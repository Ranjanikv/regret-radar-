-- 08_regret_score.sql
-- Combine stock‑out, return‑margin erosion and churn‑risk into a rupee‑based regret score
-- Idempotent view definitions for explainability (pure SQL, no UDF logic)

OPEN SCHEMA REGRET_RADAR;

-- 0️⃣ Churn risk calculation view combining CHURN_LABELS, ORDERS, and SUPPORT_TICKETS
CREATE OR REPLACE VIEW V_CHURN_RISK AS
WITH CUST_SPEND AS (
    SELECT
        CUSTOMER_ID,
        STORE_ID,
        SUM(TOTAL_AMOUNT_INR) AS TOTAL_SPENT_RUPEES,
        ROW_NUMBER() OVER (PARTITION BY CUSTOMER_ID ORDER BY COUNT(*) DESC, MAX(ORDER_DATE) DESC) AS RN
    FROM ORDERS
    GROUP BY CUSTOMER_ID, STORE_ID
),
TICKET_SUMMARY AS (
    SELECT
        CUSTOMER_ID,
        COUNT(*) AS TICKET_COUNT,
        SUM(CASE WHEN CHURN_INTENT_FLAG = 1 THEN 1 ELSE 0 END) AS CHURN_FLAG_COUNT,
        MAX(SUBJECT) AS PRIMARY_SUBJECT
    FROM SUPPORT_TICKETS
    GROUP BY CUSTOMER_ID
)
SELECT
    cl.CUSTOMER_ID,
    COALESCE(csp.STORE_ID, 'STORE_001') AS STORE_ID,
    ROUND(CAST(cl.CHURN_RISK_SCORE AS DOUBLE), 2) AS CHURN_PROB,
    COALESCE(csp.TOTAL_SPENT_RUPEES, 0.0) AS TOTAL_SPENT_RUPEES,
    ROUND(CAST(cl.CHURN_RISK_SCORE * COALESCE(csp.TOTAL_SPENT_RUPEES, 0.0) AS DOUBLE), 2) AS AT_RISK_RUPEES,
    CASE
        WHEN COALESCE(ts.CHURN_FLAG_COUNT, 0) > 0 THEN 'Explicit churn intent in support ticket: ' || COALESCE(ts.PRIMARY_SUBJECT, 'Escalation')
        WHEN cl.IS_HIGH_RISK_COHORT = 1 THEN 'High return frequency and low engagement'
        ELSE 'Inactivity risk / low order frequency'
    END AS REASON_TEXT
FROM CHURN_LABELS cl
LEFT JOIN CUST_SPEND csp ON cl.CUSTOMER_ID = csp.CUSTOMER_ID AND csp.RN = 1
LEFT JOIN TICKET_SUMMARY ts ON cl.CUSTOMER_ID = ts.CUSTOMER_ID;

-- Backward-compatibility alias for CHURN_RISK table/view
CREATE OR REPLACE VIEW CHURN_RISK AS
SELECT * FROM V_CHURN_RISK;

-- 1️⃣ Stock‑out loss (rupees) per customer / sku / store
-- Assumes table stockout_risk with columns: sku_id, store_id, expected_lost_revenue_inr
CREATE OR REPLACE VIEW v_stockout_loss AS
SELECT
    CAST(NULL AS VARCHAR(20)) AS customer_id,
    sku_id,
    store_id,
    expected_lost_revenue_inr AS stockout_loss
FROM stockout_risk;

-- 2️⃣ Return‑margin erosion (rupees) per customer / sku / store
-- Assumes table order_item_margins with columns: customer_id, sku_id, store_id, margin_erosion_rupees
CREATE OR REPLACE VIEW v_return_loss AS
SELECT
    customer_id,
    sku_id,
    CAST(NULL AS VARCHAR(20)) AS store_id,
    margin_erosion_inr AS return_loss
FROM order_item_margins;

-- 3️⃣ Churn loss (rupees) per customer / store (sku‑agnostic)
-- Assumes table churn_risk with columns: customer_id, store_id, churn_prob, total_spent_rupees
-- We treat future at‑risk revenue as churn_prob * total_spent_rupees
CREATE OR REPLACE VIEW v_churn_loss AS
SELECT
    customer_id,
    CAST(NULL AS VARCHAR(20)) AS sku_id,
    store_id,
    at_risk_rupees AS churn_loss
FROM v_churn_risk;

-- 4️⃣ Union all risk contributions (fill missing columns with 0.0)
CREATE OR REPLACE VIEW v_regret_components AS
SELECT
    customer_id,
    sku_id,
    store_id,
    COALESCE(stockout_loss, 0.0) AS stockout_loss,
    0.0 AS return_loss,
    0.0 AS churn_loss
FROM v_stockout_loss
UNION ALL
SELECT
    customer_id,
    sku_id,
    store_id,
    0.0 AS stockout_loss,
    COALESCE(return_loss, 0.0) AS return_loss,
    0.0 AS churn_loss
FROM v_return_loss
UNION ALL
SELECT
    customer_id,
    sku_id,
    store_id,
    0.0 AS stockout_loss,
    0.0 AS return_loss,
    COALESCE(churn_loss, 0.0) AS churn_loss
FROM v_churn_loss;

-- 5️⃣ Aggregate per customer / sku / store to obtain total regret score (rupees)
CREATE OR REPLACE VIEW v_regret_score AS
SELECT
    customer_id,
    sku_id,
    store_id,
    SUM(stockout_loss)   AS stockout_loss,
    SUM(return_loss)     AS return_loss,
    SUM(churn_loss)      AS churn_loss,
    (SUM(stockout_loss) + SUM(return_loss) + SUM(churn_loss)) AS regret_score_rupees
FROM v_regret_components
GROUP BY customer_id, sku_id, store_id;

-- The view v_regret_score is the single source of truth for the Regret Radar.
