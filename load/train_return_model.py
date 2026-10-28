"""Train return probability model on historical orders and stage to BucketFS."""

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

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


def extract_features(df: pd.DataFrame) -> np.ndarray:
    """Extract strictly pre-fulfillment feature matrix (NO data leakage)."""
    n = len(df)
    features = np.zeros((n, len(FEATURE_NAMES)), dtype=float)

    unit_price = df["unit_price_inr"].to_numpy(dtype=float)
    discount = df["discount_inr"].to_numpy(dtype=float)
    discount_pct = np.where(unit_price > 0, discount / unit_price, 0.0)
    qty = df["quantity"].to_numpy(dtype=float)
    cost = df["cost_price_inr"].to_numpy(dtype=float)
    is_high_size = df["size"].isin(HIGH_RETURN_SIZES).astype(float).to_numpy()

    features[:, 0] = unit_price
    features[:, 1] = discount
    features[:, 2] = discount_pct
    features[:, 3] = qty
    features[:, 4] = cost
    features[:, 5] = is_high_size

    # One-hot encode category
    cat_col = df["category"].to_numpy()
    offset = 6
    for i, c in enumerate(CATEGORIES):
        features[:, offset + i] = (cat_col == c).astype(float)

    # One-hot encode channel
    chan_col = df["channel"].to_numpy()
    offset = 6 + len(CATEGORIES)
    for j, ch in enumerate(CHANNELS):
        features[:, offset + j] = (chan_col == ch).astype(float)

    return features


def load_training_data_from_db() -> Optional[pd.DataFrame]:
    """Query orders, items, products, and return flags from Exasol."""
    try:
        import pyexasol

        from load.check_db import get_connection_config

        cfg = get_connection_config()
        conn = pyexasol.connect(**cfg)
        conn.execute("OPEN SCHEMA REGRET_RADAR")
        sql = """
        SELECT
            i.ORDER_ITEM_ID,
            i.QUANTITY,
            i.UNIT_PRICE_INR,
            i.DISCOUNT_INR,
            i.LINE_TOTAL_INR,
            p.CATEGORY,
            p.SIZE,
            p.COST_PRICE_INR,
            o.CHANNEL,
            CASE WHEN r.RETURN_ID IS NOT NULL THEN 1 ELSE 0 END AS IS_RETURNED
        FROM ORDER_ITEMS i
        JOIN ORDERS o ON i.ORDER_ID = o.ORDER_ID
        JOIN PRODUCTS p ON i.SKU_ID = p.SKU_ID
        LEFT JOIN "RETURNS" r ON i.ORDER_ITEM_ID = r.ORDER_ITEM_ID
        """
        df = conn.export_to_pandas(sql)
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as exc:
        print(f"[WARN] Unable to load training data from Exasol DB ({exc}). Trying CSV fallback.")
        return None


def load_training_data_from_csv(data_dir: Path = Path("data_gen/output")) -> pd.DataFrame:
    """Load training records directly from generated CSVs if DB unavailable."""
    df_items = pd.read_csv(data_dir / "order_items.csv")
    df_orders = pd.read_csv(data_dir / "orders.csv")
    df_products = pd.read_csv(data_dir / "products.csv")
    df_returns = pd.read_csv(data_dir / "returns.csv")

    merged = df_items.merge(
        df_orders[["order_id", "channel"]], on="order_id", how="inner"
    ).merge(
        df_products[["sku_id", "category", "size", "cost_price_inr"]], on="sku_id", how="inner"
    )
    ret_ids = set(df_returns["order_item_id"])
    merged["is_returned"] = merged["order_item_id"].isin(ret_ids).astype(int)
    return merged


def sanitize_for_cross_version_pickle(clf: GradientBoostingClassifier) -> None:
    """Remove internal RNG objects to allow unpickling across numpy/sklearn versions."""
    clf.random_state = None
    if hasattr(clf, "_rng"):
        clf._rng = None
    if hasattr(clf, "random_state_"):
        del clf.random_state_
    for row in getattr(clf, "estimators_", []):
        for est in row:
            est.random_state = None
            if hasattr(est, "_rng"):
                est._rng = None


def train_return_model(
    df: pd.DataFrame, test_size: float = 0.2, random_state: int = 42
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """Train GradientBoostingClassifier with non-leaking features and evaluate test AUC."""
    assert "is_returned" in df.columns, "Target 'is_returned' must be present."
    # Strict check: verify no post-fulfillment columns leak
    forbidden = {"return_reason", "refund_amount_inr", "return_date", "return_id"}
    leaked = forbidden.intersection(df.columns)
    assert not leaked, f"Data leakage detected! Forbidden columns: {leaked}"

    X = extract_features(df)
    y = df["is_returned"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    clf = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=4,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    # Evaluate test AUC and predictions
    test_probs = clf.predict_proba(X_test)[:, 1]
    test_preds = (test_probs >= 0.5).astype(int)
    auc_score = float(roc_auc_score(y_test, test_probs))
    train_probs = clf.predict_proba(X_train)[:, 1]
    train_auc = float(roc_auc_score(y_train, train_probs))

    metrics = {
        "train_samples": float(len(X_train)),
        "test_samples": float(len(X_test)),
        "train_auc": train_auc,
        "test_auc": auc_score,
        "overall_return_rate": float(np.mean(y)),
    }

    print("\n--- Model Training Results ---")
    print(f"Train samples: {len(X_train):,} | Test samples: {len(X_test):,}")
    print(f"Return Rate: {metrics['overall_return_rate']:.2%}")
    print(f"Train AUC: {train_auc:.4f} | Test AUC: {auc_score:.4f}")
    print("\nClassification Report (Test):")
    print(classification_report(y_test, test_preds, digits=4))

    # Top feature importances
    importances = clf.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("Top Feature Importances:")
    for rank, idx in enumerate(sorted_idx[:8], 1):
        print(f"  {rank}. {FEATURE_NAMES[idx]}: {importances[idx]:.4f}")

    # Prepare model artifact
    sanitize_for_cross_version_pickle(clf)
    bundle = {
        "model": clf,
        "feature_names": FEATURE_NAMES,
        "categories": CATEGORIES,
        "channels": CHANNELS,
        "high_return_sizes": list(HIGH_RETURN_SIZES),
        "metrics": metrics,
    }
    return bundle, metrics


def stage_model(bundle: Dict[str, Any], local_path: Path) -> List[str]:
    """Serialize model artifact to local disk and BucketFS sync path."""
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        pickle.dump(bundle, f, protocol=4)

    saved_paths = [str(local_path)]
    print(f"[OK] Staged local model artifact: {local_path}")

    # Exasol Personal BucketFS directory
    bfs_rel = Path("bfsdefault") / "default" / "models" / local_path.name
    bfs_target = (
        Path.home()
        / ".exasol"
        / "personal"
        / "deployments"
        / "default"
        / "local"
        / "runtime"
        / "exa"
        / "bucketfs"
        / bfs_rel
    )
    if bfs_target.parent.exists():
        with open(bfs_target, "wb") as f:
            pickle.dump(bundle, f, protocol=4)
        saved_paths.append(str(bfs_target))
        print(f"[OK] Replicated model into BucketFS mount: {bfs_target}")
    else:
        # Create parent and stage
        try:
            bfs_target.parent.mkdir(parents=True, exist_ok=True)
            with open(bfs_target, "wb") as f:
                pickle.dump(bundle, f, protocol=4)
            saved_paths.append(str(bfs_target))
            print(f"[OK] Created and replicated model into BucketFS mount: {bfs_target}")
        except Exception as e:
            print(f"[WARN] Could not stage directly to BucketFS mount ({e}).")

    return saved_paths


def main() -> None:
    """Run data extraction, model training, evaluation, and staging."""
    df = load_training_data_from_db()
    if df is None:
        df = load_training_data_from_csv()

    bundle, _ = train_return_model(df)
    local_model = Path("models/return_model.pkl")
    stage_model(bundle, local_model)
    print("\n[DONE] Return probability model successfully trained and staged.")


if __name__ == "__main__":
    main()
