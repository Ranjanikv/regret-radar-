"""Execute in-database demand forecasting and stockout risk scoring via Exasol Python UDF."""

import time
from pathlib import Path
from typing import Dict

from load.check_db import connect_exasol, get_connection_config
from load.load import apply_schema


def execute_forecast_pipeline(
    sql_file: Path = Path("sql/05_stockout_forecast.sql"),
) -> Dict[str, float]:
    """Execute SKU-store demand forecast and backtesting inside Exasol."""
    config = get_connection_config()
    print(f"Connecting to Exasol at {config['dsn']} for stockout forecasting...")
    with connect_exasol(config) as conn:
        print(f"Executing {sql_file}...")
        start_t = time.perf_counter()
        apply_schema(conn, sql_file)
        duration = time.perf_counter() - start_t
        print(f"UDF execution & table materialization finished in {duration:.2f}s.")

        conn.open_schema("REGRET_RADAR")
        query = """
        SELECT
            COUNT(*) AS TOTAL_SERIES,
            SUM(CASE WHEN RISK_TIER = 'CRITICAL' THEN 1 ELSE 0 END) AS CRITICAL_COUNT,
            SUM(CASE WHEN RISK_TIER = 'HIGH' THEN 1 ELSE 0 END) AS HIGH_COUNT,
            SUM(CASE WHEN RISK_TIER = 'MEDIUM' THEN 1 ELSE 0 END) AS MEDIUM_COUNT,
            SUM(CASE WHEN RISK_TIER = 'LOW' THEN 1 ELSE 0 END) AS LOW_COUNT,
            ROUND(AVG(MODEL_MAE), 3) AS AVG_MODEL_MAE,
            ROUND(AVG(BASELINE_MAE), 3) AS AVG_BASELINE_MAE,
            ROUND((1.0 - AVG(MODEL_MAE) / AVG(BASELINE_MAE)) * 100, 2) AS ACCURACY_IMPROVEMENT_PCT
        FROM STOCKOUT_RISK
        """
        row = conn.execute(query).fetchone()

        hist_query = """
        SELECT
            COUNT(CASE WHEN IS_STOCKOUT = 1 THEN 1 END) AS STOCKOUT_DAYS,
            SUM(MISSED_DEMAND_UNITS) AS TOTAL_LOST_UNITS,
            ROUND(SUM(d.MISSED_DEMAND_UNITS * p.MRP_INR), 2) AS HISTORICAL_LOST_REV
        FROM DAILY_INVENTORY d
        JOIN PRODUCTS p ON d.SKU_ID = p.SKU_ID
        """
        hist_row = conn.execute(hist_query).fetchone()

        metrics = {
            "total_series": float(row[0]),
            "critical_risk_count": float(row[1]),
            "high_risk_count": float(row[2]),
            "medium_risk_count": float(row[3]),
            "low_risk_count": float(row[4]),
            "avg_model_mae": float(row[5]),
            "avg_baseline_mae": float(row[6]),
            "accuracy_improvement_pct": float(row[7]),
            "historical_stockout_days": float(hist_row[0]),
            "historical_lost_revenue_inr": float(hist_row[2]),
            "execution_time_sec": float(round(duration, 2)),
        }

        print("\n=== Stockout Forecast & Backtest Results ===")
        print(f"Total SKU-Store Series:   {int(metrics['total_series']):,}")
        print(f"Average Model MAE:        {metrics['avg_model_mae']:.3f} units")
        print(f"Average Baseline MAE:     {metrics['avg_baseline_mae']:.3f} units (7-day lag)")
        print(f"Accuracy Improvement:     +{metrics['accuracy_improvement_pct']:.2f}% vs. baseline")
        print(f"Medium-Risk Series:       {int(metrics['medium_risk_count']):,} series (< 28 hrs)")
        print(f"Historical Lost Revenue:  ₹{metrics['historical_lost_revenue_inr']:,.2f}")
        return metrics


def main() -> None:
    """CLI entrypoint."""
    execute_forecast_pipeline()


if __name__ == "__main__":
    main()
