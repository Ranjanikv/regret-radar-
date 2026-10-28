import sys
from pathlib import Path

# Add repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.db import get_connection, run_query
from app.views_action_queue import init_action_tracking_table
import unittest.mock as mock

print("Testing direct Exasol queries used in the dashboard pages...")
con = get_connection()
print("[OK] Connected to Exasol and opened schema REGRET_RADAR.")

# 1. Executive overview queries
print("Testing Executive Overview queries...")
q1 = run_query("""
SELECT 
    COALESCE(SUM(regret_score_rupees), 0.0) AS total_regret,
    COALESCE(SUM(stockout_loss), 0.0) AS total_stockout,
    COALESCE(SUM(return_loss), 0.0) AS total_return,
    COALESCE(SUM(churn_loss), 0.0) AS total_churn,
    COUNT(DISTINCT customer_id) AS at_risk_customers,
    COUNT(DISTINCT sku_id) AS at_risk_skus,
    COUNT(DISTINCT store_id) AS at_risk_stores
FROM v_regret_score
WHERE regret_score_rupees > 0
""")
print(f"[OK] Summary: Total Regret = Rs {q1.iloc[0]['total_regret']:,.2f}")

# 2. Action Queue queries
print("Testing Action Queue queries...")
q2 = run_query("SELECT * FROM v_action_queue LIMIT 10")
print(f"[OK] Action Queue: {len(q2)} rows returned.")

# 3. Stockout queries
print("Testing Stockout queries...")
q3 = run_query("SELECT * FROM stockout_risk LIMIT 10")
print(f"[OK] Stockout Risk: {len(q3)} rows returned.")

# 4. Return Margin queries
print("Testing Order Item Margins queries...")
q4 = run_query("SELECT * FROM order_item_margins LIMIT 10")
print(f"[OK] Order Item Margins: {len(q4)} rows returned.")

# 5. Customer identity graph
print("Testing Customer Identity Graph...")
q5 = run_query("SELECT * FROM customer_identity_graph LIMIT 10")
print(f"[OK] Customer Identity Graph: {len(q5)} rows returned.")

# 6. Action tracking init
print("Testing Action Tracking table init...")
init_action_tracking_table()
print("[OK] Action tracking table initialized/verified.")

print("\nALL BACKEND QUERIES & SCHEMA OBJECTS VERIFIED SUCCESSFULLY!")
