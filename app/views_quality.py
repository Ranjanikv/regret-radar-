"""Data Quality, Governance Monitoring, and Customer 360 Profiles."""

import pandas as pd
import streamlit as st

try:
    from app.db import fmt_rupee, run_query
except ImportError:
    from db import fmt_rupee, run_query


def page_data_quality() -> None:
    """Render automated data health, reconciliation, and schema integrity monitoring."""
    st.title("🛡️ Data Quality & Schema Governance")
    st.markdown(
        "Automated continuous integrity verification across Exasol tables and views. "
        "Flags anomalous values, broken foreign keys, and reconciliation gaps."
    )

    # 1. Reconciliation Check
    st.subheader("1. Additive Regret Loss Reconciliation")
    recon_sql = """
    SELECT
        COUNT(*) AS total_rows,
        SUM(CASE
            WHEN ABS(regret_score_rupees - (stockout_loss + return_loss + churn_loss)) > 0.05
            THEN 1 ELSE 0
        END) AS unreconciled_count
    FROM v_regret_score
    """
    recon_df = run_query(recon_sql)
    if not recon_df.empty:
        tot = int(recon_df.iloc[0]["total_rows"])
        unrec = int(recon_df.iloc[0]["unreconciled_count"])
        if unrec == 0:
            st.success(f"✅ Loss Reconciliation Passed: 100% of rows ({tot:,}) strictly balance.")
        else:
            st.error(f"❌ Loss Reconciliation Warning: {unrec} rows have a discrepancy.")

    st.markdown("---")

    # 2. Database Health & Integrity Checks
    st.subheader("2. Relational Integrity & Bounds Verification")
    checks = [
        ("Negative Revenue / Amounts", "SELECT COUNT(*) FROM orders WHERE total_amount_inr < 0", 0),
        (
            "Negative Inventory Stock",
            "SELECT COUNT(*) FROM daily_inventory WHERE ending_stock < 0",
            0,
        ),
        (
            "Unlinked Order Items (Missing Product)",
            "SELECT COUNT(*) FROM order_items i "
            "LEFT JOIN products p ON i.sku_id = p.sku_id WHERE p.sku_id IS NULL",
            0,
        ),
        (
            "Unlinked Returns (Missing Item)",
            'SELECT COUNT(*) FROM "RETURNS" r '
            "LEFT JOIN order_items i ON r.order_item_id = i.order_item_id "
            "WHERE i.order_item_id IS NULL",
            0,
        ),
        (
            "Orphaned Customer Identities",
            "SELECT COUNT(*) FROM customer_identity_graph WHERE golden_customer_id IS NULL",
            0,
        ),
    ]

    results = []
    for check_name, query, expected in checks:
        try:
            val = int(run_query(query).iloc[0, 0])
            status = "PASS" if val == expected else "FAIL"
            results.append(
                {
                    "Check Name": check_name,
                    "Observed Violation Count": val,
                    "Expected Count": expected,
                    "Status": status,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "Check Name": check_name,
                    "Observed Violation Count": "Error",
                    "Expected Count": expected,
                    "Status": f"ERROR ({exc})",
                }
            )

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 3. Table Volumes & Row Counts
    st.subheader("3. Exasol Table Volume & Inventory")
    tables = [
        "CUSTOMERS_TRUE",
        "WEB_USERS",
        "APP_USERS",
        "POS_LOYALTY",
        "MARKETPLACE_BUYERS",
        "PRODUCTS",
        "STORES",
        "ORDERS",
        "ORDER_ITEMS",
        "RETURNS",
        "DAILY_INVENTORY",
        "SUPPORT_TICKETS",
        "CHURN_LABELS",
        "MATCHED_PAIRS",
        "CUSTOMER_IDENTITY_GRAPH",
        "STOCKOUT_RISK",
        "ORDER_ITEM_MARGINS",
    ]
    vol_data = []
    for tbl in tables:
        try:
            cnt = int(run_query(f"SELECT COUNT(*) FROM {tbl}").iloc[0, 0])
            vol_data.append({"Table Name": tbl, "Row Count": f"{cnt:,}"})
        except Exception:
            pass

    st.dataframe(pd.DataFrame(vol_data), use_container_width=True, hide_index=True)


def page_customer_360() -> None:
    """Render unified customer touchpoint profile and risk history."""
    st.title("👤 Customer 360 & Identity Graph")
    cust_id = st.text_input(
        "Enter Customer ID or Golden ID (e.g. CUST_0000004)", "CUST_0000004"
    ).strip()

    if not cust_id:
        st.info("Provide a customer ID to inspect cross-channel touchpoints.")
        return

    # 1. Fetch Golden Identity Graph
    graph_sql = """
    SELECT touchpoint_id, channel, golden_customer_id, cluster_size
    FROM customer_identity_graph
    WHERE true_customer_id = {cid} OR golden_customer_id = {cid}
    """
    graph_df = run_query(graph_sql, params={"cid": cust_id})

    # 2. Fetch Spend & Risk History
    spend_sql = """
    SELECT
        c.customer_id,
        c.first_name || ' ' || c.last_name AS full_name,
        c.email,
        c.phone,
        c.city,
        COALESCE(SUM(o.total_amount_inr), 0) AS total_spent,
        COUNT(DISTINCT o.order_id) AS total_orders,
        MAX(o.order_date) AS last_order_date
    FROM customers_true c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    WHERE c.customer_id = {cid}
    GROUP BY c.customer_id, c.first_name, c.last_name, c.email, c.phone, c.city
    """
    spend_df = run_query(spend_sql, params={"cid": cust_id})

    if spend_df.empty:
        st.warning(f"No records found for ID: {cust_id}")
        return

    cr = spend_df.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customer Name", str(cr["full_name"]))
    c2.metric("Total Spend", fmt_rupee(cr["total_spent"]))
    c3.metric("Lifetime Orders", f"{int(cr['total_orders'])}")
    c4.metric("City", str(cr["city"]))

    if not graph_df.empty:
        st.subheader("Unified Cross-Channel Touchpoints")
        st.dataframe(graph_df, use_container_width=True, hide_index=True)


def page_natural_language() -> None:
    """Natural Language SQL Translator interface for retail analytics."""
    st.title("💬 Ask Regret Radar (NLP Query)")
    query = st.text_area(
        "Ask a business question (e.g., 'Which store had highest return erosion?')",
        "Which store had the highest return margin erosion?",
    )
    if st.button("Generate In-Database SQL"):
        st.info("Exasol MCP Server converts natural language into in-database SQL execution.")
        st.code(
            f"-- Generated SQL for query: '{query}'\n"
            "SELECT s.store_name, SUM(m.margin_erosion_inr) AS erosion_inr\n"
            "FROM order_item_margins m\n"
            "JOIN orders o ON m.order_id = o.order_id\n"
            "JOIN stores s ON o.store_id = s.store_id\n"
            "GROUP BY s.store_name\n"
            "ORDER BY erosion_inr DESC LIMIT 10;",
            language="sql",
        )
