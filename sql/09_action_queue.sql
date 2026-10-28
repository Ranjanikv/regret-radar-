-- 09_action_queue.sql
-- Action Queue: top 50 daily actions with suggested intervention and reason.
-- Relies on v_regret_score (customer_id, sku_id, store_id, stockout_loss, return_loss, churn_loss, regret_score_rupees)

CREATE OR REPLACE VIEW v_action_queue AS
SELECT
    rs.customer_id,
    rs.sku_id,
    rs.store_id,
    rs.regret_score_rupees,
    rs.stockout_loss,
    rs.return_loss,
    rs.churn_loss,
    -- Determine which risk contributes the most
    CASE
        WHEN rs.stockout_loss >= rs.return_loss AND rs.stockout_loss >= rs.churn_loss THEN 'stockout'
        WHEN rs.return_loss  >= rs.stockout_loss AND rs.return_loss  >= rs.churn_loss THEN 'return'
        ELSE 'churn'
    END AS dominant_risk,
    -- Suggested intervention based on dominant risk
    CASE
        WHEN rs.stockout_loss >= rs.return_loss AND rs.stockout_loss >= rs.churn_loss THEN 'Increase inventory / reorder'
        WHEN rs.return_loss  >= rs.stockout_loss AND rs.return_loss  >= rs.churn_loss THEN 'Review product quality & return policy'
        ELSE 'Proactive customer outreach / retention offer'
    END AS suggested_intervention,
    -- Human‑readable reason combining the loss figures
    CASE
        WHEN rs.stockout_loss >= rs.return_loss AND rs.stockout_loss >= rs.churn_loss
            THEN 'Potential stock-out loss of ₹' || CAST(ROUND(rs.stockout_loss, 2) AS VARCHAR(30))
        WHEN rs.return_loss  >= rs.stockout_loss AND rs.return_loss  >= rs.churn_loss
            THEN 'Margin erosion from returns of ₹' || CAST(ROUND(rs.return_loss, 2) AS VARCHAR(30))
        ELSE 'Churn risk loss of ₹' || CAST(ROUND(rs.churn_loss, 2) AS VARCHAR(30))
    END AS reason
FROM v_regret_score rs
WHERE rs.regret_score_rupees > 0
ORDER BY rs.regret_score_rupees DESC
LIMIT 50;

-- The view v_action_queue provides the daily ranked action list for the UI.
