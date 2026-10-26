"""Bulk loader for synthetic CSV datasets into Exasol using pyexasol import streaming."""

import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pyexasol

from load.check_db import connect_exasol, get_connection_config

TABLE_LOAD_ORDER: List[str] = [
    "customers_true",
    "web_users",
    "app_users",
    "pos_loyalty",
    "marketplace_buyers",
    "products",
    "stores",
    "orders",
    "order_items",
    "returns",
    "daily_inventory",
    "support_tickets",
    "churn_labels",
]


def detect_row_separator(csv_file: Path) -> str:
    """Detect whether file uses CRLF or LF line endings."""
    with open(csv_file, "rb") as f:
        sample = f.read(4096)
        return "CRLF" if b"\r\n" in sample else "LF"


def apply_schema(conn: pyexasol.ExaConnection, schema_file: Path) -> None:
    """Execute SQL DDL file to ensure schema and tables exist idempotently."""
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_file}")

    sql_content = schema_file.read_text(encoding="utf-8")
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]
    for stmt in statements:
        conn.execute(stmt)


def load_table(
    conn: pyexasol.ExaConnection,
    schema_name: str,
    table_name: str,
    csv_file: Path,
    max_retries: int = 2,
) -> Tuple[int, float]:
    """Truncate destination table and bulk-import CSV data via pyexasol with retry support."""
    target_table = table_name.upper()
    row_sep = detect_row_separator(csv_file)
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            conn.execute(f'TRUNCATE TABLE "{schema_name}"."{target_table}";')
            start_t = time.perf_counter()
            conn.import_from_file(
                str(csv_file),
                (schema_name, target_table),
                import_params={"skip": 1, "row_separator": row_sep},
            )
            duration = time.perf_counter() - start_t
            count = conn.execute(
                f'SELECT COUNT(*) FROM "{schema_name}"."{target_table}";'
            ).fetchval()
            time.sleep(0.05)  # Cooldown between sequential imports
            return int(count), duration
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
            else:
                raise last_exc  # type: ignore

    return 0, 0.0


def bulk_load_all(
    data_dir: Path,
    schema_name: str = "REGRET_RADAR",
    schema_file: Path = Path("sql/01_schema.sql"),
) -> Dict[str, Tuple[int, float]]:
    """Idempotently prepare schema and load all retail dataset tables into Exasol."""
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Data directory '{data_dir}' not found. Run 'python -m data_gen.generate' first."
        )

    config = get_connection_config()
    results: Dict[str, Tuple[int, float]] = {}

    print(f"Connecting to Exasol at {config['dsn']} for bulk loading...")
    with connect_exasol(config) as conn:
        print(f"Applying schema definitions from {schema_file}...")
        apply_schema(conn, schema_file)

        print(f"\n--- Bulk Loading Tables into {schema_name} ---")
        overall_start = time.perf_counter()

        for table in TABLE_LOAD_ORDER:
            csv_path = data_dir / f"{table}.csv"
            if not csv_path.exists():
                print(f"[SKIP] CSV missing for {table} at {csv_path}")
                continue

            count, duration = load_table(conn, schema_name, table, csv_path)
            rate = (count / duration) if duration > 0 else 0.0
            results[table] = (count, duration)
            print(
                f"  -> {table.upper():<20} {count:>10,} rows in "
                f"{duration:6.2f}s ({rate:>10,.0f} rows/s)"
            )

        total_rows = sum(cnt for cnt, _ in results.values())
        total_time = time.perf_counter() - overall_start
        avg_rate = (total_rows / total_time) if total_time > 0 else 0.0
        print(
            f"\n[DONE] Loaded {total_rows:,} total rows across {len(results)} tables "
            f"in {total_time:.2f}s ({avg_rate:,.0f} rows/s)."
        )

    return results


def parse_args() -> argparse.Namespace:
    """Parse loader CLI arguments."""
    parser = argparse.ArgumentParser(description="Bulk load Regret Radar CSV datasets into Exasol")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data_gen/output"),
        help="Path to folder containing generated CSV files",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default="REGRET_RADAR",
        help="Target Exasol schema name",
    )
    parser.add_argument(
        "--schema-file",
        type=Path,
        default=Path("sql/01_schema.sql"),
        help="Path to schema DDL file",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entry point."""
    args = parse_args()
    bulk_load_all(args.data_dir, args.schema, args.schema_file)


if __name__ == "__main__":
    main()
