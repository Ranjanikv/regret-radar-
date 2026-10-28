"""Initialize Regret Radar database schema, views, and derived tables in Exasol."""

import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from load.check_db import connect_exasol, get_connection_config
from load.load import split_sql_statements

SQL_INIT_PIPELINE: List[Path] = [
    Path("sql/01_schema.sql"),
    Path("sql/02_identity_resolution.sql"),
    Path("sql/03_identity_udfs.sql"),
    Path("sql/04_run_identity.sql"),
    Path("sql/05_stockout_forecast.sql"),
    Path("sql/06_return_model.sql"),
    Path("sql/07_true_margin.sql"),
    Path("sql/08_regret_score.sql"),
    Path("sql/09_action_queue.sql"),
]


def execute_sql_file(conn, sql_path: Path) -> None:
    """Read and execute an idempotent SQL file with UDF support."""
    content = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(content)
    print(f"Executing {sql_path.name} ({len(statements)} statements)...")
    for stmt in statements:
        if stmt.strip():
            conn.execute(stmt)


def init_regret_radar(schema_name: str = "REGRET_RADAR") -> None:
    """Idempotently initialize all Regret Radar schemas, tables, UDFs, and views."""
    config = get_connection_config()
    print(f"Connecting to Exasol at {config['dsn']} as user '{config['user']}'...")
    with connect_exasol(config) as conn:
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
        conn.execute(f"OPEN SCHEMA {schema_name}")

        for sql_file in SQL_INIT_PIPELINE:
            if not sql_file.exists():
                raise FileNotFoundError(f"Required SQL file not found: {sql_file}")
            execute_sql_file(conn, sql_file)

        # Ensure ORDER_ITEM_MARGINS is populated if V_TRUE_MARGIN view exists
        try:
            row_count = conn.execute("SELECT COUNT(*) FROM ORDER_ITEM_MARGINS").fetchone()[0]
            if row_count == 0:
                print("Populating ORDER_ITEM_MARGINS from V_TRUE_MARGIN...")
                conn.execute("INSERT INTO ORDER_ITEM_MARGINS SELECT * FROM V_TRUE_MARGIN")
        except Exception as exc:
            print(f"[NOTE] ORDER_ITEM_MARGINS check/populate: {exc}")

        print("\n[OK] Regret Radar core schema, derived tables, and views are ready.")


def main() -> None:
    """Entry point for CLI initialization."""
    try:
        init_regret_radar()
    except Exception as exc:
        print(f"\n[ERROR] Initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
