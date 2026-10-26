"""Exasol Python SET-EMITS UDF for SKU-Store demand forecasting and stockout risk scoring."""

from datetime import date
from typing import Dict, List, Tuple

import numpy as np


def fit_forecast_model(
    sales: np.ndarray,
    dates: List[date],
    holdout: int = 14,
) -> Tuple[float, float, float, float, float]:
    """Train autoregressive feature model with weekly seasonality, backtesting against 7-day lag."""
    n = len(sales)
    if n < 28:
        # Fallback if insufficient history
        mean_s = float(np.mean(sales)) if n > 0 else 1.0
        return mean_s, 1.0, 1.0, 1.0, 1.0

    dows = np.array([d.weekday() for d in dates], dtype=int)

    # Feature matrix: [lag_1, lag_7, ma_7, is_weekend]
    feats = []
    targets = []
    for i in range(7, n):
        lag1 = float(sales[i - 1])
        lag7 = float(sales[i - 7])
        ma7 = float(np.mean(sales[i - 7 : i]))
        is_wknd = 1.0 if dows[i] in (5, 6) else 0.0
        feats.append([1.0, lag1, lag7, ma7, is_wknd])
        targets.append(float(sales[i]))

    X = np.array(feats, dtype=float)
    y = np.array(targets, dtype=float)

    # Train / Holdout split
    split_idx = len(X) - holdout
    X_train, y_train = X[:split_idx], y[:split_idx]
    X_test, y_test = X[split_idx:], y[split_idx:]

    # Ridge regression via normal equations (X^T X + lambda I)^-1 X^T y
    alpha = 1.0
    xtx = X_train.T @ X_train + alpha * np.eye(X.shape[1])
    xty = X_train.T @ y_train
    weights = np.linalg.solve(xtx, xty)

    # Predictions on test holdout
    y_pred_test = np.maximum(0.0, X_test @ weights)
    # Baseline: same day last week (lag_7 is col 2)
    y_base_test = X_test[:, 2]

    # Metrics
    mae_model = float(np.mean(np.abs(y_test - y_pred_test)))
    rmse_model = float(np.sqrt(np.mean((y_test - y_pred_test) ** 2)))
    mae_base = float(np.mean(np.abs(y_test - y_base_test)))
    rmse_base = float(np.sqrt(np.mean((y_test - y_base_test) ** 2)))

    # Forecast next day
    next_dow = (dows[-1] + 1) % 7
    next_feats = np.array([
        1.0,
        float(sales[-1]),
        float(sales[-7]),
        float(np.mean(sales[-7:])),
        1.0 if next_dow in (5, 6) else 0.0,
    ])
    next_pred = float(np.maximum(0.0, next_feats @ weights))

    return next_pred, mae_model, rmse_model, mae_base, rmse_base


def compute_stockout_metrics(
    current_stock: int,
    predicted_demand: float,
    unit_mrp: float,
    residual_std: float = 1.5,
) -> Dict[str, object]:
    """Compute hours to stockout, lost units, expected lost revenue, and risk tier."""
    daily_pred = max(0.1, predicted_demand)
    hourly_rate = daily_pred / 14.0  # 14 operating retail store hours/day

    if hourly_rate <= 0 or current_stock >= daily_pred * 3:
        hours_to_stockout = 999.0
    else:
        hours_to_stockout = round(min(999.0, current_stock / hourly_rate), 1)

    expected_lost_units = max(0.0, daily_pred - current_stock)
    expected_lost_rev = round(expected_lost_units * unit_mrp, 2)

    # Normal approximation for stockout probability: P(Demand > Stock)
    z = (current_stock - daily_pred) / max(0.8, residual_std)
    # Simple sigmoid approx to normal CDF: 1 / (1 + exp(1.7 * z))
    stockout_prob = round(float(1.0 / (1.0 + np.exp(1.6 * z))), 3)

    if hours_to_stockout <= 6.0 and expected_lost_units > 0:
        tier = "CRITICAL"
    elif hours_to_stockout <= 14.0:
        tier = "HIGH"
    elif hours_to_stockout <= 28.0:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return {
        "current_stock": int(current_stock),
        "predicted_demand": round(daily_pred, 2),
        "hours_to_stockout": hours_to_stockout,
        "expected_lost_units": round(expected_lost_units, 2),
        "expected_lost_revenue_inr": expected_lost_rev,
        "stockout_probability": stockout_prob,
        "risk_tier": tier,
    }


def run(ctx):
    """Exasol SET-EMITS entrypoint grouped by store_id and sku_id."""
    dates: List[date] = []
    sales: List[int] = []
    ending_stocks: List[int] = []
    mrp = 1000.0
    store = None
    sku = None

    while True:
        store = ctx.store_id
        sku = ctx.sku_id
        dates.append(ctx.inv_date)
        sales.append(int(ctx.units_sold))
        ending_stocks.append(int(ctx.ending_stock))
        if ctx.mrp_inr is not None:
            mrp = float(ctx.mrp_inr)
        if not ctx.next():
            break

    if not dates or store is None or sku is None:
        return

    # Sort chronology
    order = sorted(range(len(dates)), key=lambda k: dates[k])
    dates = [dates[k] for k in order]
    sales_arr = np.array([sales[k] for k in order], dtype=int)
    ending_stocks = [ending_stocks[k] for k in order]

    pred, mae_m, _, mae_b, _ = fit_forecast_model(sales_arr, dates, holdout=14)
    metrics = compute_stockout_metrics(ending_stocks[-1], pred, mrp)

    ctx.emit(
        store,
        sku,
        metrics["current_stock"],
        metrics["predicted_demand"],
        metrics["hours_to_stockout"],
        metrics["expected_lost_units"],
        metrics["expected_lost_revenue_inr"],
        metrics["stockout_probability"],
        metrics["risk_tier"],
        round(mae_m, 3),
        round(mae_b, 3),
        dates[-1],
    )
