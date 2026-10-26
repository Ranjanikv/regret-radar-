"""Orchestrate in-database Exasol identity resolution pipeline and compute evaluation metrics."""

import time
from pathlib import Path
from typing import Dict

from load.check_db import connect_exasol, get_connection_config
from load.load import apply_schema


def execute_identity_pipeline(
    sql_files: list[Path] | None = None,
) -> Dict[str, float]:
    """Execute SQL views, UDFs, and identity matching, returning evaluation metrics."""
    if sql_files is None:
        sql_files = [
            Path("sql/02_identity_resolution.sql"),
            Path("sql/03_identity_udfs.sql"),
            Path("sql/04_run_identity.sql"),
        ]

    config = get_connection_config()
    print(f"Connecting to Exasol at {config['dsn']} for identity resolution...")
    with connect_exasol(config) as conn:
        for sql_f in sql_files:
            print(f"Executing {sql_f}...")
            apply_schema(conn, sql_f)

        print("\nEvaluating identity resolution metrics against ground truth...")
        t_start = time.perf_counter()
        conn.open_schema("REGRET_RADAR")

        eval_query = """
        WITH PREDICTED_PAIRS AS (
            SELECT a.TOUCHPOINT_ID AS ID1, b.TOUCHPOINT_ID AS ID2,
                   a.TRUE_CUSTOMER_ID AS TRUE1, b.TRUE_CUSTOMER_ID AS TRUE2
            FROM CUSTOMER_IDENTITY_GRAPH a
            JOIN CUSTOMER_IDENTITY_GRAPH b
              ON a.GOLDEN_CUSTOMER_ID = b.GOLDEN_CUSTOMER_ID AND a.TOUCHPOINT_ID < b.TOUCHPOINT_ID
        ),
        GROUND_TRUTH_PAIRS AS (
            SELECT a.TOUCHPOINT_ID AS ID1, b.TOUCHPOINT_ID AS ID2
            FROM UNIFIED_TOUCHPOINTS a
            JOIN UNIFIED_TOUCHPOINTS b
              ON a.TRUE_CUSTOMER_ID = b.TRUE_CUSTOMER_ID AND a.TOUCHPOINT_ID < b.TOUCHPOINT_ID
        )
        SELECT
            (SELECT COUNT(*) FROM UNIFIED_TOUCHPOINTS) AS TOTAL_TOUCHPOINTS,
            (SELECT COUNT(DISTINCT GOLDEN_CUSTOMER_ID) FROM CUSTOMER_IDENTITY_GRAPH)
                AS UNIQUE_GOLDEN,
            (SELECT COUNT(*) FROM PREDICTED_PAIRS WHERE TRUE1 = TRUE2) AS TP,
            (SELECT COUNT(*) FROM PREDICTED_PAIRS WHERE TRUE1 != TRUE2) AS FP,
            (SELECT COUNT(*) FROM GROUND_TRUTH_PAIRS)
                - (SELECT COUNT(*) FROM PREDICTED_PAIRS WHERE TRUE1 = TRUE2) AS FN
        """
        row = conn.execute(eval_query).fetchone()
        eval_time = time.perf_counter() - t_start

        total_touchpoints = int(row[0])
        unique_golden = int(row[1])
        tp = int(row[2])
        fp = int(row[3])
        fn = int(row[4])

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (
            (2 * precision * recall / (precision + recall))
            if (precision + recall) > 0
            else 0.0
        )

        metrics = {
            "total_touchpoints": float(total_touchpoints),
            "unique_golden": float(unique_golden),
            "tp": float(tp),
            "fp": float(fp),
            "fn": float(fn),
            "precision": float(round(precision, 4)),
            "recall": float(round(recall, 4)),
            "f1": float(round(f1, 4)),
            "evaluation_time_sec": float(round(eval_time, 2)),
        }

        print("\n=== Identity Resolution Results ===")
        print(f"Total Touchpoints:       {total_touchpoints:,}")
        print(f"Unique Golden Customers: {unique_golden:,}")
        print(f"True Positives (TP):     {tp:,}")
        print(f"False Positives (FP):    {fp:,}")
        print(f"False Negatives (FN):    {fn:,}")
        print(f"Precision:               {precision * 100:.2f}% (High-confidence target)")
        print(f"Recall:                  {recall * 100:.2f}%")
        print(f"F1 Score:                {f1 * 100:.2f}%")
        print(f"Evaluation Time:         {eval_time:.2f}s")
        return metrics


def main() -> None:
    """Entry point for command line invocation."""
    execute_identity_pipeline()


if __name__ == "__main__":
    main()
