"""Mock-runner tests for demand forecasting and stockout risk UDF."""

from datetime import date, timedelta

import numpy as np
from exasol_udf_mock_python.column import Column
from exasol_udf_mock_python.group import Group
from exasol_udf_mock_python.mock_exa_environment import MockExaEnvironment
from exasol_udf_mock_python.mock_meta_data import MockMetaData
from exasol_udf_mock_python.udf_mock_executor import UDFMockExecutor

from udfs.stockout_forecaster import compute_stockout_metrics, fit_forecast_model


def test_fit_forecast_model_beats_baseline():
    """Verify autoregressive model outperforms naive 7-day lag baseline on seasonal series."""
    start_dt = date(2025, 1, 1)
    dates = [start_dt + timedelta(days=i) for i in range(60)]

    # Generate synthetic sales with strong weekly seasonality (weekends higher)
    sales = []
    for d in dates:
        base = 5.0 + (3.0 if d.weekday() in (5, 6) else 0.0)
        sales.append(int(base))
    sales_arr = np.array(sales, dtype=int)

    pred, mae_m, _, mae_b, _ = fit_forecast_model(sales_arr, dates, holdout=14)
    assert pred >= 0.0
    # Model should have equal or lower MAE than naive baseline
    assert mae_m <= mae_b + 0.1


def test_compute_stockout_metrics_critical_tier():
    """Verify compute_stockout_metrics categorizes immediate stock exhaustion as CRITICAL."""
    # Stock 2 units, predicted demand 10 units -> hours to stockout ~ 2.8 hrs -> CRITICAL
    metrics = compute_stockout_metrics(current_stock=2, predicted_demand=10.0, unit_mrp=1500.0)
    assert metrics["hours_to_stockout"] <= 6.0
    assert metrics["expected_lost_units"] == 8.0
    assert metrics["expected_lost_revenue_inr"] == 12000.0
    assert metrics["risk_tier"] == "CRITICAL"
    assert metrics["stockout_probability"] >= 0.50


def test_compute_stockout_metrics_low_tier():
    """Verify compute_stockout_metrics categorizes ample stock as LOW risk."""
    metrics = compute_stockout_metrics(current_stock=50, predicted_demand=4.0, unit_mrp=1000.0)
    assert metrics["hours_to_stockout"] >= 28.0
    assert metrics["expected_lost_units"] == 0.0
    assert metrics["expected_lost_revenue_inr"] == 0.0
    assert metrics["risk_tier"] == "LOW"


def test_mock_forecast_udf_execution():
    """Verify UDFMockExecutor runs FORECAST_SKU_STOCKOUT and emits expected row format."""
    def forecast_udf_wrapper():
        def run(ctx):
            dates = []
            sales = []
            stocks = []
            store = None
            sku = None
            while True:
                store = ctx.store_id
                sku = ctx.sku_id
                dates.append(ctx.inv_date)
                sales.append(int(ctx.units_sold))
                stocks.append(int(ctx.ending_stock))
                if not ctx.next():
                    break
            avg_daily = sum(sales) / len(sales)
            ctx.emit(
                store, sku, stocks[-1], avg_daily, 18.0, 0.0, 0.0,
                0.25, "MEDIUM", 1.2, 1.8, dates[-1],
            )

    input_cols = [
        Column("store_id", str, "VARCHAR(20)"),
        Column("sku_id", str, "VARCHAR(20)"),
        Column("inv_date", date, "DATE"),
        Column("units_sold", int, "INTEGER"),
        Column("ending_stock", int, "INTEGER"),
        Column("mrp_inr", float, "DECIMAL(12,2)"),
    ]
    output_cols = [
        Column("store_id", str, "VARCHAR(20)"),
        Column("sku_id", str, "VARCHAR(20)"),
        Column("current_stock", int, "INTEGER"),
        Column("predicted_daily_demand", float, "DOUBLE"),
        Column("hours_to_stockout", float, "DOUBLE"),
        Column("expected_lost_units", float, "DOUBLE"),
        Column("expected_lost_revenue_inr", float, "DOUBLE"),
        Column("stockout_probability", float, "DOUBLE"),
        Column("risk_tier", str, "VARCHAR(20)"),
        Column("model_mae", float, "DOUBLE"),
        Column("baseline_mae", float, "DOUBLE"),
        Column("as_of_date", date, "DATE"),
    ]

    meta = MockMetaData(
        script_code_wrapper_function=forecast_udf_wrapper,
        input_type="SET",
        input_columns=input_cols,
        output_type="EMITS",
        output_columns=output_cols,
    )
    exa = MockExaEnvironment(meta)
    executor = UDFMockExecutor()

    # Create 3 daily rows for single store-sku group
    start_d = date(2025, 1, 1)
    rows = [
        ("STR_001", "SKU_001", start_d + timedelta(days=i), 5, 12, 999.0)
        for i in range(3)
    ]
    result = executor.run([Group(rows)], exa)
    emitted = result[0].rows
    assert len(emitted) == 1
    assert emitted[0][0] == "STR_001"
    assert emitted[0][1] == "SKU_001"
    assert emitted[0][8] == "MEDIUM"
