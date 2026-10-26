# Evaluation Results

This document records the empirical evaluation metrics for Regret Radar's machine learning and rule-based scoring modules running natively inside Exasol.

---

## 1. Identity Resolution (Customer Unification)

Evaluated against `CUSTOMERS_TRUE` ground truth across all 4 fragmented retail touchpoints (`WEB_USERS`, `APP_USERS`, `POS_LOYALTY`, `MARKETPLACE_BUYERS`).

### Pipeline Stages
1. **SQL Blocking**: Generates candidate pairs based on normalized phone, email domain/prefix, and name/pincode criteria (55,277 candidate pairs).
2. **SET-EMITS UDF Scoring (`SCORE_IDENTITY_PAIRS`)**: Multidimensional similarity scoring across Levenshtein string distance, Jaro-Winkler name similarity, phone normalization, and pincode matching with a high-confidence threshold of `>= 0.72`.
3. **Graph Connected Components (`RESOLVE_CONNECTED_COMPONENTS`)**: Disjoint-set clustering resolving transitive pairwise matches into unified `GOLDEN_CUSTOMER_ID` identifiers.

### Measured Metrics
- **Dataset Scale**: `small` (5,000 true customers, 11,189 fragmented touchpoints)
- **Unified Golden Customer Entities**: 7,232
- **True Positives (TP)**: 4,851 pairs
- **False Positives (FP)**: 5 pairs
- **False Negatives (FN)**: 4,496 pairs
- **Pairwise Precision**: **99.90%** (4,851 / 4,856)
- **Pairwise Recall**: **51.90%** (4,851 / 9,347)
- **F1 Score**: **68.31%**
- **In-Database Execution Time**: ~0.15s evaluation time (< 4.5s total UDF scoring and clustering)

> [!NOTE]
> Per architectural guidelines, the identity resolution model strongly favours **precision (99.90%)** over recall to prevent catastrophic false merges (erroneously combining distinct real-world customer profiles).

---

## 2. Stock-Out Demand Forecasting & Regret Scoring

Evaluated per SKU-store across 500 active retail time series using Exasol SET-EMITS UDF parallelism (`GROUP BY d.STORE_ID, d.SKU_ID`).

### Methodology
- **Training Data**: First 76 days of daily inventory sales and stock history.
- **Holdout Test Set**: Last 14 days (14 held-out evaluation days per SKU-store).
- **Light Model**: Autoregressive Ridge model inside Exasol Python SLC featuring:
  - 1-day lag (`lag_1`)
  - 7-day seasonal lag (`lag_7`)
  - 7-day rolling moving average (`ma_7`)
  - Day-of-week indicator (`is_weekend`)
- **Benchmark Baseline**: Naive "same as last week" baseline (7-day lag $y_{t-7}$).

### Backtest Performance Comparison (500 Series, 14 Held-Out Days)
| Metric | Naive 7-Day Lag Baseline | Regret Radar Ridge Model | Relative Improvement |
|---|---|---|---|
| **Mean Absolute Error (MAE)** | **2.426 units** | **1.910 units** | **+21.28% lower error** |

### Operational Impact & Regret Metrics
- **Total SKU-Store Series Evaluated**: 500 series (45,000 daily observations)
- **Medium-Risk Stockouts (< 28 hrs buffer)**: 93 SKU-store locations
- **Historical Stockout Events in Dataset**: 2,355 stockout incidents
- **Total Units Lost Due to Stockouts**: 8,967 units
- **Historical Lost Revenue from Stockouts**: **₹30,883,115.00** (~₹3.09 Crore)
- **In-Database Execution Time**: **~8.2s** for full distributed training, holdout backtesting, and forward prediction across all 500 series.
