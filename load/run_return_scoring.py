"""Orchestrate return probability UDF registration, True Margin scoring, and ranking."""

import time
from pathlib import Path
from typing import Any, Dict

import pyexasol

from load.check_db import get_connection_config
from load.load import split_sql_statements


def execute_sql_file(conn: pyexasol.ExaConnection, sql_path: Path) -> None:
    """Read and execute an idempotent SQL file with UDF support."""
    content = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(content)
    print(f"Executing {sql_path.name} ({len(statements)} statements)...")
    for stmt in statements:
        if stmt.strip():
            conn.execute(stmt)


def run_return_pipeline() -> Dict[str, Any]:
    """Execute UDF creation, True Margin scoring, and print top margin erosion."""
    start_t = time.perf_counter()
    cfg = get_connection_config()
    conn = pyexasol.connect(**cfg)
    conn.execute("OPEN SCHEMA REGRET_RADAR")

    # 1. Register UDF and create Views/DDL
    sql_dir = Path("sql")
    execute_sql_file(conn, sql_dir / "06_return_model.sql")
    execute_sql_file(conn, sql_dir / "07_true_margin.sql")

    # 2. Populate ORDER_ITEM_MARGINS from V_TRUE_MARGIN
    print("Scoring in-database True Margin for all order items...")
    score_start = time.perf_counter()
    conn.execute("TRUNCATE TABLE ORDER_ITEM_MARGINS")
    conn.execute("INSERT INTO ORDER_ITEM_MARGINS SELECT * FROM V_TRUE_MARGIN")
    score_duration = time.perf_counter() - score_start

    count_res = conn.execute("SELECT count(*) FROM ORDER_ITEM_MARGINS").fetchone()[0]
    print(f"[OK] Scored {count_res:,} items in {score_duration:.2f}s.")

    # 3. Retrieve Top Margin-Eroded Products
    top_prods_sql = """
    SELECT
        SKU_ID,
        PRODUCT_NAME,
        CATEGORY,
        SIZE,
        TOTAL_UNITS_SOLD,
        TOTAL_REVENUE_INR,
        TOTAL_NOMINAL_MARGIN_INR,
        TOTAL_TRUE_MARGIN_INR,
        TOTAL_MARGIN_EROSION_INR,
        MARGIN_EROSION_PCT
    FROM RANKED_PRODUCTS_MARGIN_EROSION
    ORDER BY TOTAL_MARGIN_EROSION_INR DESC
    LIMIT 5
    """
    prods = conn.execute(top_prods_sql).fetchall()

    print("\n=== TOP 5 PRODUCTS WITH BIGGEST MARGIN EROSION ===")
    for p in prods:
        m_pct = float(p[9])
        print(
            f"  {p[0]} | {p[1]:<30} | {p[2]} ({p[3]}) | Sold: {int(p[4]):,} units | "
            f"Revenue: INR {float(p[5]):,.0f} | Nominal: INR {float(p[6]):,.0f} | "
            f"True: INR {float(p[7]):,.0f} | Erosion: INR {float(p[8]):,.0f} ({m_pct:.1f}%)"
        )

    # 4. Retrieve Top Margin-Eroded Orders
    top_orders_sql = """
    SELECT
        ORDER_ID,
        CUSTOMER_ID,
        CHANNEL,
        ORDER_DATE,
        ORDER_TOTAL_INR,
        ORDER_NOMINAL_MARGIN_INR,
        ORDER_TRUE_MARGIN_INR,
        ORDER_MARGIN_EROSION_INR,
        MARGIN_EROSION_PCT
    FROM RANKED_ORDERS_MARGIN_EROSION
    ORDER BY ORDER_MARGIN_EROSION_INR DESC
    LIMIT 5
    """
    orders = conn.execute(top_orders_sql).fetchall()

    print("\n=== TOP 5 ORDERS WITH BIGGEST MARGIN EROSION ===")
    for o in orders:
        print(
            f"  {o[0]} | Customer: {o[1]} | {o[2]:<11} | Date: {o[3]} | "
            f"Total: INR {float(o[4]):,.0f} | Nominal: INR {float(o[5]):,.0f} | "
            f"True: INR {float(o[6]):,.0f} | Erosion: INR {float(o[7]):,.0f} ({float(o[8]):.1f}%)"
        )

    total_duration = time.perf_counter() - start_t
    print(f"\n[DONE] Pipeline completed in {total_duration:.2f}s.")
    return {
        "items_scored": count_res,
        "score_duration": score_duration,
        "top_products": prods,
        "top_orders": orders,
    }


if __name__ == "__main__":
    run_return_pipeline()
