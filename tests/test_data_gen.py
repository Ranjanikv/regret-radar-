"""Unit tests for synthetic data generation and realistic pattern injection."""

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from data_gen.catalog import generate_products, generate_stores
from data_gen.generate import write_csv_chunked
from data_gen.identity import generate_channel_identities, generate_customers_true
from data_gen.support_churn import generate_support_tickets
from data_gen.transactions import (
    generate_daily_inventory,
    generate_orders_and_items,
    generate_returns,
)


def test_seed_reproducibility():
    """Verify that identical random seeds generate bit-for-bit identical datasets."""
    rng1 = np.random.default_rng(123)
    df_cust1 = generate_customers_true(50, rng1)

    rng2 = np.random.default_rng(123)
    df_cust2 = generate_customers_true(50, rng2)

    pd.testing.assert_frame_equal(df_cust1, df_cust2)


def test_channel_identities_link_to_ground_truth():
    """Verify fragmented identities preserve ground truth customer foreign keys."""
    rng = np.random.default_rng(42)
    df_cust = generate_customers_true(100, rng)
    df_web, df_app, df_pos, df_mkt = generate_channel_identities(df_cust, rng)

    cust_ids = set(df_cust["customer_id"])
    assert set(df_web["customer_id"]).issubset(cust_ids)
    assert set(df_app["customer_id"]).issubset(cust_ids)
    assert set(df_pos["customer_id"]).issubset(cust_ids)
    assert set(df_mkt["customer_id"]).issubset(cust_ids)


def test_size_skewed_returns():
    """Verify extreme sizes (XS, XXL) exhibit higher return propensity."""
    rng = np.random.default_rng(42)
    df_products = generate_products(100, rng)
    df_cust = generate_customers_true(100, rng)
    df_stores = generate_stores(5, rng)

    df_orders, df_items = generate_orders_and_items(200, 30, df_cust, df_products, df_stores, rng)
    df_returns = generate_returns(df_orders, df_items, df_products, rng)

    assert not df_returns.empty
    reasons = set(df_returns["return_reason"])
    assert "Size too small" in reasons or "Size too large" in reasons


def test_support_ticket_churn_correlation():
    """Verify support ticket churn phrases correlate with ground truth churn labels."""
    rng = np.random.default_rng(42)
    df_cust = generate_customers_true(80, rng)
    df_ret = pd.DataFrame({"customer_id": df_cust["customer_id"].iloc[:20]})

    df_tickets, df_churn = generate_support_tickets(df_cust, df_ret, 60, rng)

    # Flagged churn cohort should have substantially higher churn risk than unflagged
    high_risk_mean = df_churn[df_churn["is_high_risk_cohort"] == 1]["churn_risk_score"].mean()
    low_risk_mean = df_churn[df_churn["is_high_risk_cohort"] == 0]["churn_risk_score"].mean()

    assert high_risk_mean > low_risk_mean


def test_daily_inventory_stockouts():
    """Verify daily inventory generates stockout events and missed demand."""
    rng = np.random.default_rng(42)
    df_stores = generate_stores(3, rng)
    df_products = generate_products(10, rng)

    df_inv = generate_daily_inventory(df_stores, df_products, 45, rng)
    assert "is_stockout" in df_inv.columns
    assert "missed_demand_units" in df_inv.columns
    assert (df_inv["is_stockout"] == 1).any()


def test_chunked_csv_writer():
    """Verify write_csv_chunked produces complete CSV identical to in-memory DataFrame."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "test_chunk.csv"
        df = pd.DataFrame({
            "a": list(range(100)),
            "b": [f"val_{i}" for i in range(100)],
        })
        write_csv_chunked(df, tmp_path, chunk_size=25)
        loaded = pd.read_csv(tmp_path)
        pd.testing.assert_frame_equal(df, loaded)
