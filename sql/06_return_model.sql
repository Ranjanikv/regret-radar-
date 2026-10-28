-- 06_return_model.sql
-- In-database return probability scoring via scikit-learn GradientBoosting model loaded from BucketFS

OPEN SCHEMA REGRET_RADAR;

-- 1. SCALAR Python UDF: Score Return Probability for an Order Item
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT SCORE_RETURN_PROBABILITY(
    category VARCHAR(50),
    size VARCHAR(20),
    channel VARCHAR(30),
    unit_price_inr DOUBLE,
    discount_inr DOUBLE,
    quantity DOUBLE,
    cost_price_inr DOUBLE
)
RETURNS DOUBLE AS
import os
from pathlib import Path
import pickle
import numpy as np

CATEGORIES = [
    "Ethnic Wear",
    "Western Wear",
    "Footwear",
    "Home & Living",
    "Beauty & Grooming",
    "Fashion Accessories",
]
CHANNELS = ["Web", "App", "POS", "Marketplace"]
HIGH_RETURN_SIZES = {"XS", "XXL"}

FEATURE_NAMES = [
    "unit_price_inr",
    "discount_inr",
    "discount_pct",
    "quantity",
    "cost_price_inr",
    "is_high_return_size",
] + [f"cat_{c}" for c in CATEGORIES] + [f"chan_{ch}" for ch in CHANNELS]

_MODEL_CACHE = {}


def load_staged_model():
    if "bundle" in _MODEL_CACHE:
        return _MODEL_CACHE["bundle"]

    candidate_paths = [
        Path("/buckets/bfsdefault/default/models/return_model.pkl"),
        Path("models/return_model.pkl"),
    ]
    for p in candidate_paths:
        if p.exists():
            try:
                with open(p, "rb") as f:
                    bundle = pickle.load(f)
                    _MODEL_CACHE["bundle"] = bundle
                    return bundle
            except Exception:
                pass
    return None


def fallback_return_probability(category, size):
    is_apparel = category in {"Ethnic Wear", "Western Wear", "Footwear"}
    is_extreme = size in HIGH_RETURN_SIZES
    if is_apparel:
        return 0.28 if is_extreme else 0.14
    return 0.05


def run(ctx):
    cat = str(ctx[0] or "Ethnic Wear")
    sz = str(ctx[1] or "M")
    chan = str(ctx[2] or "Web")
    price = float(ctx[3] or 0.0)
    disc = float(ctx[4] or 0.0)
    disc_pct = (disc / price) if price > 0 else 0.0
    qty = float(ctx[5] or 1.0)
    cost = float(ctx[6] or 0.0)

    bundle = load_staged_model()
    if bundle is None or "model" not in bundle:
        return fallback_return_probability(cat, sz)

    clf = bundle["model"]
    x = np.zeros((1, len(FEATURE_NAMES)), dtype=float)
    x[0, 0] = price
    x[0, 1] = disc
    x[0, 2] = disc_pct
    x[0, 3] = qty
    x[0, 4] = cost
    x[0, 5] = 1.0 if sz in HIGH_RETURN_SIZES else 0.0

    offset = 6
    for i, c in enumerate(CATEGORIES):
        if cat == c:
            x[0, offset + i] = 1.0
            break

    offset = 6 + len(CATEGORIES)
    for j, ch in enumerate(CHANNELS):
        if chan == ch:
            x[0, offset + j] = 1.0
            break

    try:
        prob = clf.predict_proba(x)[0, 1]
        return round(float(prob), 4)
    except Exception:
        return fallback_return_probability(cat, sz)
/
