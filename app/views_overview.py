"""Executive Overview and Risk Intelligence Dashboard for Regret Radar."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

try:
    from app.db import fmt_rupee, run_query
except ImportError:
    from db import fmt_rupee, run_query


def page_executive_overview() -> None:
    """Render the primary executive landing page with KPIs and macro analytics."""
    st.title("🎯 Executive Risk Intelligence")
    st.caption(
        "Real-time unified retail risk scoring: Stock-outs, Return margin erosion, "
        "and Churn signals. Powered by In-Database Exasol Analytics."
    )

    # 1. Fetch Snapshot & Aggregated Risk Figures
    summary_sql = """
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
    """
    summary_df = run_query(summary_sql)
    if summary_df.empty:
        st.warning("No exposure data available in schema REGRET_RADAR.")
        return

    row = summary_df.iloc[0]
    total_regret = float(row["total_regret"])
    total_stockout = float(row["total_stockout"])
    total_return = float(row["total_return"])
    total_churn = float(row["total_churn"])
    cust_count = int(row["at_risk_customers"])
    sku_count = int(row["at_risk_skus"])
    store_count = int(row["at_risk_stores"])

    # 2. Executive KPI Cards
    st.subheader("Macro Risk Exposure (Snapshot)")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(
        "Total Regret Exposure",
        fmt_rupee(total_regret),
        help="Combined rupee exposure across all 3 risk vectors",
    )
    kpi2.metric(
        "Silent Churn Loss",
        fmt_rupee(total_churn),
        help="Customer lifetime spend at risk from predicted churn",
    )
    kpi3.metric(
        "Stock-Out Loss",
        fmt_rupee(total_stockout),
        help="Expected lost revenue from inventory stock-outs",
    )
    kpi4.metric(
        "Return Margin Erosion",
        fmt_rupee(total_return),
        help="Erosion of net margin from reverse logistics and write-offs",
    )

    cnt1, cnt2, cnt3 = st.columns(3)
    cnt1.metric("Impacted Customers", f"{cust_count:,}")
    cnt2.metric("Impacted SKUs", f"{sku_count:,}")
    cnt3.metric("Impacted Retail Stores", f"{store_count:,}")

    st.markdown("---")

    # 3. Top 5 Actionable Interventions
    st.subheader("⚡ Top 5 Priority Interventions Today")
    top5_sql = """
    SELECT
        customer_id,
        sku_id,
        store_id,
        regret_score_rupees,
        dominant_risk,
        suggested_intervention,
        reason
    FROM v_action_queue
    ORDER BY regret_score_rupees DESC
    LIMIT 5
    """
    top5_df = run_query(top5_sql)
    if not top5_df.empty:
        display_top5 = top5_df.copy()
        display_top5["regret_score_rupees"] = display_top5["regret_score_rupees"].apply(fmt_rupee)
        display_top5.columns = [
            "Customer ID",
            "SKU ID",
            "Store ID",
            "Regret Exposure",
            "Dominant Risk",
            "Suggested Action",
            "Reason",
        ]
        st.dataframe(display_top5, use_container_width=True, hide_index=True)
    else:
        st.info("No immediate priority actions pending.")

    st.markdown("---")

    # 4. Analytics Visualizations Section
    st.subheader("📊 Risk Composition & Concentration Analysis")
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("**Dominant Risk Distribution (Rupees)**")
        risk_dist_sql = """
        SELECT
            dominant_risk,
            COALESCE(SUM(regret_score_rupees), 0.0) AS exposure_inr,
            COUNT(*) AS action_count
        FROM v_action_queue
        GROUP BY dominant_risk
        ORDER BY exposure_inr DESC
        """
        risk_dist = run_query(risk_dist_sql)
        if not risk_dist.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ["#e74c3c", "#f39c12", "#3498db"]
            ax.pie(
                risk_dist["exposure_inr"],
                labels=risk_dist["dominant_risk"].str.upper(),
                autopct="%1.1f%%",
                startangle=140,
                colors=colors[: len(risk_dist)],
            )
            ax.axis("equal")
            st.pyplot(fig)
            plt.close(fig)

    with col_chart2:
        st.markdown("**Exposure by Component Vector**")
        comp_df = pd.DataFrame(
            {
                "Vector": ["Silent Churn", "Stock-Outs", "Return Erosion"],
                "Rupees": [total_churn, total_stockout, total_return],
            }
        )
        st.bar_chart(comp_df.set_index("Vector"))

    # 5. Pareto Concentration & Store-Level Risk
    col_pareto, col_store = st.columns(2)

    with col_pareto:
        st.markdown("**Pareto Curve: Regret Concentration**")
        pareto_sql = """
        SELECT regret_score_rupees
        FROM v_action_queue
        WHERE regret_score_rupees > 0
        ORDER BY regret_score_rupees DESC
        """
        pareto_raw = run_query(pareto_sql)
        if not pareto_raw.empty and total_regret > 0:
            scores = pareto_raw["regret_score_rupees"].to_numpy(dtype=float)
            cum_pct = (np.cumsum(scores) / np.sum(scores)) * 100.0
            fig_p, ax_p = plt.subplots(figsize=(6, 3.8))
            ax_p.plot(range(1, len(cum_pct) + 1), cum_pct, color="#8e44ad", lw=2.5)
            ax_p.axhline(80, color="gray", linestyle="--", alpha=0.7, label="80% Exposure Mark")
            ax_p.set_xlabel("Top Interventions Rank")
            ax_p.set_ylabel("Cumulative Share (%)")
            ax_p.set_ylim([0, 105])
            ax_p.grid(True, alpha=0.3)
            ax_p.legend(loc="lower right")
            st.pyplot(fig_p)
            plt.close(fig_p)

    with col_store:
        st.markdown("**Top 10 Stores by Risk Exposure**")
        store_sql = """
        SELECT
            COALESCE(s.store_name, v.store_id) AS store_name,
            ROUND(SUM(v.regret_score_rupees), 2) AS exposure_inr
        FROM v_regret_score v
        LEFT JOIN stores s ON v.store_id = s.store_id
        WHERE v.store_id IS NOT NULL AND v.regret_score_rupees > 0
        GROUP BY COALESCE(s.store_name, v.store_id)
        ORDER BY exposure_inr DESC
        LIMIT 10
        """
        store_df = run_query(store_sql)
        if not store_df.empty:
            st.bar_chart(store_df.set_index("store_name"))

    st.caption(
        "ℹ️ Data source: Analytical views `V_REGRET_SCORE` and `V_ACTION_QUEUE` in Exasol."
    )
