"""Vectorized order, order items, return events, and daily inventory with seasonal demand."""

from datetime import timedelta
from typing import List, Tuple

import numpy as np
import pandas as pd

from data_gen.config import CHANNELS, HIGH_RETURN_SIZES, RETURN_REASONS, START_DATE


def generate_orders_and_items(
    num_orders: int,
    num_days: int,
    df_customers: pd.DataFrame,
    df_products: pd.DataFrame,
    df_stores: pd.DataFrame,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate orders and line items with weekly and festival demand patterns."""
    cust_ids = df_customers["customer_id"].to_numpy()
    store_ids = df_stores["store_id"].to_numpy()
    sku_ids = df_products["sku_id"].to_numpy()
    mrps = dict(zip(df_products["sku_id"], df_products["mrp_inr"], strict=False))

    # Seasonal weighting across days
    day_weights = np.ones(num_days, dtype=float)
    for d in range(num_days):
        dt = START_DATE + timedelta(days=d)
        if dt.weekday() in (5, 6):  # Weekend bump
            day_weights[d] *= 1.55
        if 40 <= d <= 52:  # Festive season spike (e.g., Diwali window)
            day_weights[d] *= 2.40
    day_weights /= day_weights.sum()

    chosen_days = rng.choice(num_days, size=num_orders, p=day_weights)
    order_dates = [START_DATE + timedelta(days=int(d)) for d in chosen_days]

    chosen_cust = rng.choice(cust_ids, size=num_orders)
    chosen_store = rng.choice(store_ids, size=num_orders)
    chosen_channel = rng.choice(CHANNELS, size=num_orders, p=[0.35, 0.35, 0.20, 0.10])

    order_ids = [f"ORD_{i:08d}" for i in range(1, num_orders + 1)]

    # Basket item generation (1 to 3 items per order)
    items_per_order = rng.choice([1, 2, 3], size=num_orders, p=[0.65, 0.25, 0.10])
    total_items = int(np.sum(items_per_order))

    item_order_ids = np.repeat(order_ids, items_per_order)
    item_skus = rng.choice(sku_ids, size=total_items)
    quantities = rng.choice([1, 2], size=total_items, p=[0.92, 0.08])

    unit_prices = np.array([mrps[sku] for sku in item_skus], dtype=int)
    discounts = (unit_prices * rng.uniform(0.0, 0.25, size=total_items)).astype(int)
    line_totals = (unit_prices - discounts) * quantities

    df_items = pd.DataFrame({
        "order_item_id": [f"ITEM_{i:09d}" for i in range(1, total_items + 1)],
        "order_id": item_order_ids,
        "sku_id": item_skus,
        "quantity": quantities,
        "unit_price_inr": unit_prices,
        "discount_inr": discounts,
        "line_total_inr": line_totals,
    })

    order_totals = df_items.groupby("order_id", sort=False)["line_total_inr"].sum().to_dict()
    totals_arr = np.array([order_totals[oid] for oid in order_ids])

    df_orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": chosen_cust,
        "store_id": chosen_store,
        "channel": chosen_channel,
        "order_date": order_dates,
        "total_amount_inr": totals_arr,
    })

    return df_orders, df_items


def generate_returns(
    df_orders: pd.DataFrame,
    df_items: pd.DataFrame,
    df_products: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate return requests skewed towards Apparel, Footwear, and extreme sizes."""
    sku_risk_map = dict(zip(df_products["sku_id"], df_products["base_return_risk"], strict=False))
    sku_size_map = dict(zip(df_products["sku_id"], df_products["size"], strict=False))
    order_date_map = dict(zip(df_orders["order_id"], df_orders["order_date"], strict=False))
    order_cust_map = dict(zip(df_orders["order_id"], df_orders["customer_id"], strict=False))

    item_risks = np.array([sku_risk_map.get(s, 0.08) for s in df_items["sku_id"]])
    return_mask = rng.random(len(df_items)) < item_risks

    ret_items = df_items[return_mask].copy()
    ret_count = len(ret_items)
    if ret_count == 0:
        return pd.DataFrame(columns=[
            "return_id", "order_item_id", "order_id", "sku_id",
            "customer_id", "return_date", "return_reason", "refund_amount_inr"
        ])

    reasons: List[str] = []
    return_dates = []
    for _, row in ret_items.iterrows():
        sku = row["sku_id"]
        size = sku_size_map.get(sku, "M")
        ord_date = order_date_map.get(row["order_id"], START_DATE)
        days_after = rng.integers(2, 14)
        return_dates.append(ord_date + timedelta(days=int(days_after)))

        if size in HIGH_RETURN_SIZES:
            reasons.append(rng.choice(["Size too small", "Size too large"], p=[0.55, 0.45]))
        else:
            reasons.append(rng.choice(RETURN_REASONS))

    return pd.DataFrame({
        "return_id": [f"RET_{i:08d}" for i in range(1, ret_count + 1)],
        "order_item_id": ret_items["order_item_id"].to_numpy(),
        "order_id": ret_items["order_id"].to_numpy(),
        "sku_id": ret_items["sku_id"].to_numpy(),
        "customer_id": [order_cust_map[oid] for oid in ret_items["order_id"]],
        "return_date": return_dates,
        "return_reason": reasons,
        "refund_amount_inr": ret_items["line_total_inr"].to_numpy(),
    })


def generate_daily_inventory(
    df_stores: pd.DataFrame,
    df_products: pd.DataFrame,
    num_days: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate daily inventory records tracking sales, stockouts, and demand spikes."""
    store_ids = df_stores["store_id"].to_numpy()
    sku_ids = df_products["sku_id"].to_numpy()

    # Sample active store-sku pairs (subset for fast vectorized execution)
    s_idx = rng.integers(0, len(store_ids), size=min(1200, len(store_ids) * len(sku_ids)))
    k_idx = rng.integers(0, len(sku_ids), size=len(s_idx))
    pairs = list(set(zip(store_ids[s_idx], sku_ids[k_idx], strict=False)))

    records = []
    for store, sku in pairs[:500]:
        curr_stock = rng.integers(12, 35)
        for d in range(num_days):
            dt = START_DATE + timedelta(days=d)
            # Demand spike during festive window or weekends
            festive_boost = 2.5 if 40 <= d <= 52 else (1.4 if dt.weekday() in (5, 6) else 1.0)
            daily_demand = int(rng.poisson(lam=4.0) * festive_boost)

            units_sold = min(curr_stock, daily_demand)
            missed = max(0, daily_demand - curr_stock)
            is_stockout = 1 if missed > 0 or curr_stock == 0 else 0
            curr_stock -= units_sold

            replenish = rng.integers(10, 25) if curr_stock < 6 else 0
            curr_stock += replenish

            records.append({
                "inventory_date": dt,
                "store_id": store,
                "sku_id": sku,
                "beginning_stock": curr_stock + units_sold - replenish,
                "units_received": replenish,
                "units_sold": units_sold,
                "ending_stock": curr_stock,
                "is_stockout": is_stockout,
                "missed_demand_units": missed,
            })

    return pd.DataFrame(records)
