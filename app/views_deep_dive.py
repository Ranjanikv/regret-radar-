"""Deep-dive analytics for Stock-out Forecasting and Return Margin Erosion."""

import streamlit as st

try:
    from app.db import fmt_rupee, run_query
except ImportError:
    from db import fmt_rupee, run_query


def page_stockout_analytics() -> None:
    """Render the stock-out forecasting and inventory risk analytics page."""
    st.title("📦 In-Database SKU Demand Forecasting & Stock-Out Risk")
    st.markdown(
        "Powered by Exasol Python UDF `FORECAST_SKU_STOCKOUT` running in-database with "
        "`GROUP BY` parallelism. Evaluates daily inventory, historical sales velocity, "
        "and predicts hours to stock-out."
    )

    # 1. Summary metrics
    metrics_sql = """
    SELECT
        COUNT(*) AS total_sku_stores,
        SUM(CASE WHEN risk_tier = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
        SUM(CASE WHEN risk_tier = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
        COALESCE(SUM(expected_lost_revenue_inr), 0.0) AS total_lost_rev,
        COALESCE(AVG(model_mae), 0.0) AS avg_model_mae,
        COALESCE(AVG(baseline_mae), 0.0) AS avg_base_mae
    FROM stockout_risk
    """
    m_df = run_query(metrics_sql)
    if not m_df.empty:
        r = m_df.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("SKU-Store Forecasts", f"{int(r['total_sku_stores']):,}")
        c2.metric("Critical / High Risk", f"{int(r['critical_count'] + r['high_count'])}")
        c3.metric("Expected Lost Revenue", fmt_rupee(r["total_lost_rev"]))
        improvement = (
            ((r["avg_base_mae"] - r["avg_model_mae"]) / r["avg_base_mae"] * 100)
            if r["avg_base_mae"] > 0
            else 0
        )
        c4.metric(
            "Model vs Baseline MAE",
            f"{r['avg_model_mae']:.2f} vs {r['avg_base_mae']:.2f}",
            delta=f"{improvement:+.1f}% error reduction",
        )

    st.markdown("---")

    # 2. Critical Stockout Table
    st.subheader("High-Risk Stockout Alerts (Immediate Reorder Required)")
    tbl_sql = """
    SELECT
        s.store_id,
        COALESCE(st.store_name, s.store_id) AS store_name,
        s.sku_id,
        p.product_name,
        p.category,
        s.current_stock,
        s.predicted_daily_demand,
        s.hours_to_stockout,
        s.expected_lost_units,
        s.expected_lost_revenue_inr,
        s.risk_tier,
        s.model_mae,
        s.baseline_mae
    FROM stockout_risk s
    JOIN products p ON s.sku_id = p.sku_id
    LEFT JOIN stores st ON s.store_id = st.store_id
    WHERE s.expected_lost_revenue_inr > 0 OR s.risk_tier IN ('CRITICAL', 'HIGH')
    ORDER BY s.expected_lost_revenue_inr DESC
    LIMIT 100
    """
    tbl_df = run_query(tbl_sql)
    if not tbl_df.empty:
        display_tbl = tbl_df.copy()
        display_tbl["expected_lost_revenue_inr"] = display_tbl["expected_lost_revenue_inr"].apply(
            fmt_rupee
        )
        st.dataframe(display_tbl, use_container_width=True, hide_index=True)
    else:
        st.info("No critical stockout risks detected in the active inventory snapshot.")


def page_return_margin_analytics() -> None:
    """Render the True Margin and return margin erosion analytics page."""
    st.title("↩️ Return-Margin Erosion & True Margin Analytics")
    st.markdown(
        "Analyzes post-purchase return behavior and reverse logistics costs. "
        "Calculates **True Margin = Nominal Margin - (Return Logistics + Write-Off Cost)**."
    )

    # 1. Summary KPIs
    margin_kpi_sql = """
    SELECT
        COALESCE(SUM(revenue_inr), 0.0) AS total_revenue,
        COALESCE(SUM(nominal_margin_inr), 0.0) AS nominal_margin,
        COALESCE(SUM(true_margin_inr), 0.0) AS true_margin,
        COALESCE(SUM(margin_erosion_inr), 0.0) AS total_erosion,
        AVG(return_probability) AS avg_return_prob
    FROM order_item_margins
    """
    kpi_df = run_query(margin_kpi_sql)
    if not kpi_df.empty:
        kr = kpi_df.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gross Revenue", fmt_rupee(kr["total_revenue"]))
        c2.metric("Nominal Margin", fmt_rupee(kr["nominal_margin"]))
        c3.metric("True Net Margin", fmt_rupee(kr["true_margin"]))
        erosion_pct = (
            (kr["total_erosion"] / kr["nominal_margin"] * 100)
            if kr["nominal_margin"] > 0
            else 0.0
        )
        c4.metric(
            "Margin Erosion (Loss)",
            fmt_rupee(kr["total_erosion"]),
            delta=f"-{erosion_pct:.1f}%",
            delta_color="inverse",
        )

    st.markdown("---")

    # 2. Category Level Margin Erosion
    st.subheader("Return Erosion by Product Category")
    cat_sql = """
    SELECT
        category,
        ROUND(SUM(nominal_margin_inr), 2) AS nominal_margin,
        ROUND(SUM(true_margin_inr), 2) AS true_margin,
        ROUND(SUM(margin_erosion_inr), 2) AS margin_erosion,
        ROUND(AVG(return_probability) * 100, 1) AS avg_return_pct
    FROM order_item_margins
    GROUP BY category
    ORDER BY margin_erosion DESC
    """
    cat_df = run_query(cat_sql)
    if not cat_df.empty:
        st.bar_chart(cat_df.set_index("category")[["nominal_margin", "true_margin"]])

    # 3. Top Products with Highest Margin Erosion
    st.subheader("Top 20 Products Impacted by Returns")
    prod_sql = """
    SELECT
        sku_id,
        product_name,
        category,
        size,
        ROUND(SUM(revenue_inr), 2) AS total_revenue,
        ROUND(SUM(true_margin_inr), 2) AS true_margin,
        ROUND(SUM(margin_erosion_inr), 2) AS total_erosion,
        ROUND(AVG(return_probability) * 100, 1) AS return_risk_pct
    FROM order_item_margins
    GROUP BY sku_id, product_name, category, size
    ORDER BY total_erosion DESC
    LIMIT 20
    """
    prod_df = run_query(prod_sql)
    if not prod_df.empty:
        disp_prod = prod_df.copy()
        disp_prod["total_revenue"] = disp_prod["total_revenue"].apply(fmt_rupee)
        disp_prod["true_margin"] = disp_prod["true_margin"].apply(fmt_rupee)
        disp_prod["total_erosion"] = disp_prod["total_erosion"].apply(fmt_rupee)
        disp_prod["return_risk_pct"] = disp_prod["return_risk_pct"].apply(lambda v: f"{v:.1f}%")
        st.dataframe(disp_prod, use_container_width=True, hide_index=True)
