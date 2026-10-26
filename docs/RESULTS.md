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
