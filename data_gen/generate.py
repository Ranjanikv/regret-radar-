"""CLI entrypoint for seeded, vectorized synthetic retail data generation in chunks."""

import argparse
import time
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from data_gen.catalog import generate_products, generate_stores
from data_gen.config import SCALES
from data_gen.identity import generate_channel_identities, generate_customers_true
from data_gen.support_churn import generate_support_tickets
from data_gen.transactions import (
    generate_daily_inventory,
    generate_orders_and_items,
    generate_returns,
)


def write_csv_chunked(df: pd.DataFrame, dest_path: Path, chunk_size: int = 50_000) -> None:
    """Stream DataFrame to CSV in manageable chunks to preserve bounded memory footprint."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if df.empty:
        df.to_csv(dest_path, index=False)
        return

    total_rows = len(df)
    for start_idx in range(0, total_rows, chunk_size):
        chunk = df.iloc[start_idx : start_idx + chunk_size]
        is_first = start_idx == 0
        chunk.to_csv(
            dest_path,
            mode="w" if is_first else "a",
            header=is_first,
            index=False,
        )


def generate_all(scale_name: str, seed: int, output_dir: Path) -> Dict[str, int]:
    """Execute seeded dataset generation across all 13 retail tables."""
    scale = SCALES[scale_name]
    rng = np.random.default_rng(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"--- Generating dataset for scale '{scale_name}' (Seed: {seed}) ---")
    start_t = time.perf_counter()

    # 1. Identity & Ground truth
    print("[1/5] Generating customers & fragmented channel identities...")
    df_customers = generate_customers_true(scale.num_customers, rng)
    df_web, df_app, df_pos, df_mkt = generate_channel_identities(df_customers, rng)

    # 2. Products & Stores
    print("[2/5] Generating catalog (products & stores)...")
    df_products = generate_products(scale.num_products, rng)
    df_stores = generate_stores(scale.num_stores, rng)

    # 3. Orders, Items & Returns
    print("[3/5] Generating seasonal orders, items, and size-skewed returns...")
    df_orders, df_items = generate_orders_and_items(
        scale.num_orders, scale.num_days, df_customers, df_products, df_stores, rng
    )
    df_returns = generate_returns(df_orders, df_items, df_products, rng)

    # 4. Daily Inventory & Stockouts
    print("[4/5] Generating store inventory with demand spikes & stockout events...")
    df_inv = generate_daily_inventory(df_stores, df_products, scale.num_days, rng)

    # 5. Support Tickets & Ground Truth Churn Labels
    print("[5/5] Generating support tickets and correlated churn labels...")
    df_tickets, df_churn = generate_support_tickets(df_customers, df_returns, scale.num_days, rng)

    tables: Dict[str, pd.DataFrame] = {
        "customers_true": df_customers,
        "web_users": df_web,
        "app_users": df_app,
        "pos_loyalty": df_pos,
        "marketplace_buyers": df_mkt,
        "products": df_products,
        "stores": df_stores,
        "orders": df_orders,
        "order_items": df_items,
        "returns": df_returns,
        "daily_inventory": df_inv,
        "support_tickets": df_tickets,
        "churn_labels": df_churn,
    }

    row_counts = {}
    print(f"\nWriting tables to {output_dir} in chunks of {scale.chunk_size:,} rows...")
    for table_name, df in tables.items():
        csv_file = output_dir / f"{table_name}.csv"
        write_csv_chunked(df, csv_file, scale.chunk_size)
        row_counts[table_name] = len(df)
        print(f"  -> {table_name}.csv: {len(df):,} rows")

    duration = time.perf_counter() - start_t
    total_recs = sum(row_counts.values())
    print(f"\n[DONE] Successfully generated {total_recs:,} total records in {duration:.2f}s.")
    return row_counts


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Regret Radar Seeded Synthetic Data Generator")
    parser.add_argument(
        "--scale",
        type=str,
        choices=["small", "medium", "large"],
        default="small",
        help="Dataset scale: small (~100k events), medium (~5M events), large (~50M events)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data_gen/output"),
        help="Directory to write output CSV files",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for command line invocation."""
    args = parse_args()
    generate_all(args.scale, args.seed, args.output_dir)


if __name__ == "__main__":
    main()
