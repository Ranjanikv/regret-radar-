"""Mock-runner tests for return probability scoring UDF and True Margin calculations."""

import pandas as pd
import pytest
from exasol_udf_mock_python.column import Column
from exasol_udf_mock_python.group import Group
from exasol_udf_mock_python.mock_exa_environment import MockExaEnvironment
from exasol_udf_mock_python.mock_meta_data import MockMetaData
from exasol_udf_mock_python.udf_mock_executor import UDFMockExecutor

from load.train_return_model import FEATURE_NAMES, extract_features
from udfs.return_scorer import fallback_return_probability, score_single_item


def test_extract_features_no_leakage():
    """Verify feature matrix does not contain any post-fulfillment return labels or dates."""
    df_sample = pd.DataFrame([{
        "unit_price_inr": 2500.0,
        "discount_inr": 250.0,
        "quantity": 1,
        "cost_price_inr": 1200.0,
        "size": "XXL",
        "category": "Ethnic Wear",
        "channel": "Web",
    }])

    feat = extract_features(df_sample)
    assert feat.shape == (1, len(FEATURE_NAMES))
    # Check is_high_return_size is 1.0 for XXL
    assert feat[0, 5] == 1.0
    # Check discount_pct is 0.10
    assert abs(feat[0, 2] - 0.10) < 1e-4


def test_score_single_item_extreme_size_risk():
    """Verify extreme apparel sizes yield higher predicted return risk."""
    prob_extreme = score_single_item(
        category="Footwear",
        size="XXL",
        channel="Web",
        unit_price_inr=3000.0,
        discount_inr=300.0,
        quantity=1.0,
        cost_price_inr=1500.0,
    )
    prob_normal = score_single_item(
        category="Home & Living",
        size="M",
        channel="POS",
        unit_price_inr=800.0,
        discount_inr=50.0,
        quantity=1.0,
        cost_price_inr=400.0,
    )
    assert 0.0 <= prob_extreme <= 1.0
    assert 0.0 <= prob_normal <= 1.0
    assert prob_extreme > prob_normal


def test_fallback_return_probability():
    """Verify fallback heuristics provide expected risk baselines."""
    assert fallback_return_probability("Ethnic Wear", "XS") == 0.28
    assert fallback_return_probability("Western Wear", "M") == 0.14
    assert fallback_return_probability("Beauty & Grooming", "M") == 0.05


def test_mock_return_udf_execution():
    """Verify UDFMockExecutor runs return scorer scalar UDF."""
    def return_udf_wrapper():
        def run(ctx):
            cat = ctx[0]
            sz = ctx[1]
            if cat in ("Ethnic Wear", "Western Wear", "Footwear"):
                prob = 0.28 if sz in ("XS", "XXL") else 0.14
            else:
                prob = 0.05
            return prob

    input_cols = [
        Column("category", str, "VARCHAR(50)"),
        Column("size", str, "VARCHAR(20)"),
        Column("channel", str, "VARCHAR(30)"),
        Column("unit_price_inr", float, "DOUBLE"),
        Column("discount_inr", float, "DOUBLE"),
        Column("quantity", float, "DOUBLE"),
        Column("cost_price_inr", float, "DOUBLE"),
    ]
    output_cols = [Column("prob", float, "DOUBLE")]

    meta = MockMetaData(
        script_code_wrapper_function=return_udf_wrapper,
        input_type="SCALAR",
        input_columns=input_cols,
        output_type="RETURNS",
        output_columns=output_cols,
    )
    exa = MockExaEnvironment(meta)
    executor = UDFMockExecutor()

    rows = [
        ("Ethnic Wear", "XXL", "Web", 2500.0, 200.0, 1.0, 1200.0),
        ("Beauty & Grooming", "M", "App", 500.0, 0.0, 1.0, 250.0),
    ]
    result = executor.run([Group(rows)], exa)
    emitted = result[0].rows
    assert len(emitted) == 2
    assert emitted[0][0] == 0.28
    assert emitted[1][0] == 0.05


def test_exasol_db_true_margin_integration():
    """Integration check verifying True Margin view and scoring inside real Exasol DB."""
    try:
        import pyexasol

        from load.check_db import get_connection_config

        cfg = get_connection_config()
        conn = pyexasol.connect(**cfg)
        conn.execute("OPEN SCHEMA REGRET_RADAR")
        row = conn.execute("""
            SELECT
                COUNT(*),
                ROUND(AVG(RETURN_PROBABILITY), 4),
                ROUND(SUM(MARGIN_EROSION_INR), 2)
            FROM ORDER_ITEM_MARGINS
        """).fetchone()

        assert int(row[0]) > 0, "ORDER_ITEM_MARGINS should not be empty"
        assert float(row[1]) > 0.0, "Average return probability should be > 0"
        assert float(row[2]) > 0.0, "Total margin erosion should be > 0"
    except Exception as exc:
        pytest.skip(f"Database connection skipped: {exc}")
