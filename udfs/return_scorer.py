"""Exasol Python SCALAR UDF for in-database return probability scoring using staged model."""

import pickle
from pathlib import Path
from typing import Any, Dict, Optional

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

_MODEL_CACHE: Dict[str, Any] = {}


def load_staged_model() -> Optional[Any]:
    """Load cached model bundle from BucketFS mount or local fallback."""
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


def fallback_return_probability(category: str, size: str) -> float:
    """Calibrated rule-based probability if model is unreadable."""
    is_apparel = category in {"Ethnic Wear", "Western Wear", "Footwear"}
    is_extreme = size in HIGH_RETURN_SIZES
    if is_apparel:
        return 0.28 if is_extreme else 0.14
    return 0.05


def score_single_item(
    category: Optional[str],
    size: Optional[str],
    channel: Optional[str],
    unit_price_inr: Optional[float],
    discount_inr: Optional[float],
    quantity: Optional[float],
    cost_price_inr: Optional[float],
) -> float:
    """Calculate return probability using GradientBoosting model or calibrated fallback."""
    cat = str(category or "Ethnic Wear")
    sz = str(size or "M")
    chan = str(channel or "Web")
    price = float(unit_price_inr or 0.0)
    disc = float(discount_inr or 0.0)
    disc_pct = (disc / price) if price > 0 else 0.0
    qty = float(quantity or 1.0)
    cost = float(cost_price_inr or 0.0)

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

    # Category one-hot
    offset = 6
    for i, c in enumerate(CATEGORIES):
        if cat == c:
            x[0, offset + i] = 1.0
            break

    # Channel one-hot
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


def run(ctx: Any) -> float:
    """Entrypoint for Exasol SCALAR UDF."""
    return score_single_item(
        category=ctx[0],
        size=ctx[1],
        channel=ctx[2],
        unit_price_inr=ctx[3],
        discount_inr=ctx[4],
        quantity=ctx[5],
        cost_price_inr=ctx[6],
    )
