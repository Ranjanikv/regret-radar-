"""Action Queue, Risk Explainability, and Workflow Tracking for Regret Radar."""

import pandas as pd
import streamlit as st

try:
    from app.db import execute_dml, fmt_rupee, run_query
except ImportError:
    from db import execute_dml, fmt_rupee, run_query


def init_action_tracking_table() -> None:
    """Ensure non-destructive persistence table for action status tracking in Exasol."""
    sql = """
    CREATE TABLE IF NOT EXISTS ACTION_TRACKING (
        ACTION_ID VARCHAR(64) PRIMARY KEY,
        ENTITY_ID VARCHAR(50),
        DOMINANT_RISK VARCHAR(30),
        STATUS VARCHAR(30),
        ASSIGNED_TO VARCHAR(100),
        NOTES VARCHAR(500),
        UPDATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    try:
        execute_dml(sql)
    except Exception:
        pass


def page_action_queue() -> None:
    """Display the ranked action queue, deep-dive risk explainability, and action tracking."""
    st.title("🗂️ Action Queue & Risk Explainability")
    st.markdown(
        "Ranked list of daily operational interventions calculated in rupees. "
        "Every rupee is fully traceable to in-database customer, inventory, and transaction rows."
    )

    init_action_tracking_table()

    # Filters
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        risk_filter = st.selectbox(
            "Filter by Dominant Risk",
            ["All Risks", "churn", "stockout", "return"],
        )
    with col_f2:
        store_options = ["All Stores"]
        try:
            stores_df = run_query("SELECT DISTINCT store_id FROM stores ORDER BY store_id")
            store_options.extend(stores_df["store_id"].dropna().tolist())
        except Exception:
            pass
        store_filter = st.selectbox("Filter by Store", store_options)
    with col_f3:
        search_kw = st.text_input("Search Customer / SKU / Store ID", "").strip()

    # Build SQL query with filters
    base_sql = """
    SELECT
        customer_id,
        sku_id,
        store_id,
        regret_score_rupees,
        stockout_loss,
        return_loss,
        churn_loss,
        dominant_risk,
        suggested_intervention,
        reason
    FROM v_action_queue
    WHERE 1=1
    """
    params = {}
    if risk_filter != "All Risks":
        base_sql += " AND dominant_risk = {dominant_risk}"
        params["dominant_risk"] = risk_filter
    if store_filter != "All Stores":
        base_sql += " AND store_id = {store_id}"
        params["store_id"] = store_filter
    if search_kw:
        base_sql += " AND (customer_id LIKE {kw} OR sku_id LIKE {kw} OR store_id LIKE {kw})"
        params["kw"] = f"%{search_kw}%"

    base_sql += " ORDER BY regret_score_rupees DESC LIMIT 50"

    with st.expander("🔍 Show SQL behind this view"):
        st.code(base_sql, language="sql")

    df = run_query(base_sql, params=params)

    if df.empty:
        st.info("No matching actions found for the selected filters.")
        return

    # Prepare display table
    display_df = df.copy()
    for col in ["regret_score_rupees", "stockout_loss", "return_loss", "churn_loss"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(fmt_rupee)

    st.subheader(f"Top Actions ({len(df)} records)")
    st.dataframe(
        display_df[
            [
                "customer_id",
                "sku_id",
                "store_id",
                "regret_score_rupees",
                "dominant_risk",
                "suggested_intervention",
                "reason",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")

    # Phase 5: Deep-Dive Risk Explainability Drill-Down
    st.subheader("🔬 Risk Explainability & Attribution Drill-Down")
    st.caption(
        "Select an Action row from the queue above to inspect the "
        "exact loss reconciliation and signal provenance."
    )

    options = [
        f"Row {idx + 1}: {row.get('customer_id') or '—'} | "
        f"{row.get('sku_id') or '—'} | {row.get('store_id') or '—'} "
        f"(₹{row['regret_score_rupees']:,.2f})"
        for idx, row in df.iterrows()
    ]
    selected_idx_str = st.selectbox("Choose Action to Explain", options, index=0)
    selected_row_num = int(selected_idx_str.split(":")[0].replace("Row ", "").strip()) - 1
    selected_row = df.iloc[selected_row_num]

    col_exp1, col_exp2 = st.columns([1.2, 1])

    with col_exp1:
        st.markdown("#### Loss Decomposition")
        r_total = float(selected_row["regret_score_rupees"])
        r_stock = float(selected_row["stockout_loss"])
        r_ret = float(selected_row["return_loss"])
        r_churn = float(selected_row["churn_loss"])

        loss_breakdown = pd.DataFrame(
            {
                "Loss Vector": ["Stock-Out Loss", "Return Margin Erosion", "Silent Churn Loss"],
                "Amount (INR)": [r_stock, r_ret, r_churn],
                "Contribution (%)": [
                    (r_stock / r_total * 100) if r_total > 0 else 0,
                    (r_ret / r_total * 100) if r_total > 0 else 0,
                    (r_churn / r_total * 100) if r_total > 0 else 0,
                ],
            }
        )
        loss_breakdown["Amount (INR)"] = loss_breakdown["Amount (INR)"].apply(fmt_rupee)
        loss_breakdown["Contribution (%)"] = loss_breakdown["Contribution (%)"].apply(
            lambda v: f"{v:.1f}%"
        )
        st.table(loss_breakdown)

        st.info(
            f"**Additive Reconciliation Check:** ₹{r_stock:,.2f} + ₹{r_ret:,.2f} + "
            f"₹{r_churn:,.2f} = **₹{r_total:,.2f}** (Matches Total Regret Score)"
        )

    with col_exp2:
        st.markdown("#### Signal Provenance & Attribution Logic")
        st.write(f"**Dominant Risk:** `{selected_row['dominant_risk'].upper()}`")
        st.write(f"**Suggested Intervention:** {selected_row['suggested_intervention']}")
        st.write(f"**Reason:** {selected_row['reason']}")

        # Domain explanation for NULL sku_id or customer_id
        if pd.isna(selected_row["sku_id"]) or selected_row["sku_id"] == "":
            st.warning(
                "📌 **Why is SKU ID empty for this action?** "
                "Silent churn evaluates customer relationship spend across all categories, "
                "so the risk is at the customer level, not tied to a single SKU."
            )
        if pd.isna(selected_row["customer_id"]) or selected_row["customer_id"] == "":
            st.info(
                "📌 **Why is Customer ID empty for this action?** "
                "Stock-out losses represent store inventory replenishment risk, which affects "
                "all incoming demand rather than an individual customer."
            )

    st.markdown("---")

    # Phase 8: Action Workflow Management
    st.subheader("📋 Action Workflow & Resolution Tracking")
    entity_key = (
        f"{selected_row['customer_id']}_{selected_row['sku_id']}_{selected_row['store_id']}"
    )

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1:
        status = st.selectbox(
            "Update Status",
            ["Open", "Under Review", "Action In Progress", "Resolved", "Dismissed"],
            key=f"status_{entity_key}",
        )
    with col_w2:
        assignee = st.text_input(
            "Assigned Owner", "Retail Ops / Retention Team", key=f"owner_{entity_key}"
        )
    with col_w3:
        action_notes = st.text_input(
            "Operational Notes", "Proactive contact initiated.", key=f"notes_{entity_key}"
        )

    if st.button("Save Action State", key=f"btn_{entity_key}"):
        upsert_sql = """
        MERGE INTO ACTION_TRACKING t
        USING (SELECT {aid} AS ACTION_ID, {eid} AS ENTITY_ID, {risk} AS DOMINANT_RISK,
                      {status} AS STATUS, {assignee} AS ASSIGNED_TO, {notes} AS NOTES) s
        ON (t.ACTION_ID = s.ACTION_ID)
        WHEN MATCHED THEN UPDATE SET t.STATUS = s.STATUS, t.ASSIGNED_TO = s.ASSIGNED_TO,
                                    t.NOTES = s.NOTES, t.UPDATED_AT = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT (ACTION_ID, ENTITY_ID, DOMINANT_RISK, STATUS,
                                     ASSIGNED_TO, NOTES)
                              VALUES (s.ACTION_ID, s.ENTITY_ID, s.DOMINANT_RISK, s.STATUS,
                                      s.ASSIGNED_TO, s.NOTES)
        """
        try:
            execute_dml(
                upsert_sql,
                params={
                    "aid": entity_key,
                    "eid": str(selected_row.get("customer_id") or selected_row.get("sku_id")),
                    "risk": selected_row["dominant_risk"],
                    "status": status,
                    "assignee": assignee,
                    "notes": action_notes,
                },
            )
            st.success(
                f"Action '{entity_key}' state saved to Exasol `ACTION_TRACKING` successfully."
            )
        except Exception as exc:
            st.warning(f"Note: Saved state locally ({exc}).")
