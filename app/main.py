"""Streamlit app for Regret Radar: Unified Retail Risk Intelligence Platform.

Powered by in-database Exasol analytics, machine learning, and probabilistic record linkage.
MIT licensed.
"""

import sys
from pathlib import Path
from typing import Callable, Dict

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from app.db import execute_dml, fmt_rupee, get_connection, load_db_config, run_query
    from app.views_action_queue import page_action_queue
    from app.views_deep_dive import page_return_margin_analytics, page_stockout_analytics
    from app.views_models import page_model_evaluation, page_what_if_simulator
    from app.views_overview import page_executive_overview
    from app.views_quality import (
        page_customer_360,
        page_data_quality,
        page_natural_language,
    )
except ImportError:
    from db import execute_dml, fmt_rupee, get_connection, load_db_config, run_query  # noqa: E402
    from views_action_queue import page_action_queue  # noqa: E402
    from views_deep_dive import page_return_margin_analytics, page_stockout_analytics  # noqa: E402
    from views_models import page_model_evaluation, page_what_if_simulator  # noqa: E402
    from views_overview import page_executive_overview  # noqa: E402
    from views_quality import (  # noqa: E402
        page_customer_360,
        page_data_quality,
        page_natural_language,
    )

__all__ = [
    "execute_dml",
    "fmt_rupee",
    "get_connection",
    "load_db_config",
    "run_query",
]

NAVIGATION_PAGES: Dict[str, Callable[[], None]] = {
    " Executive Overview": page_executive_overview,
    " Action Queue & Explainability": page_action_queue,
    " Stock-Out Forecasting Analytics": page_stockout_analytics,
    " Return-Margin & True Margin": page_return_margin_analytics,
    " Data Science Model Evaluation": page_model_evaluation,
    " What-If Scenario Simulator": page_what_if_simulator,
    " Data Quality & Schema Health": page_data_quality,
    " Customer 360 & Identity Graph": page_customer_360,
    " Ask Regret Radar (NLP Query)": page_natural_language,
}


def main() -> None:
    """Initialize Streamlit layout, sidebar navigation, and route to active view."""
    st.set_page_config(
        page_title="Regret Radar | Retail Risk Intelligence",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.title(" Regret Radar")
    st.sidebar.caption("Retail Risk Intelligence on Exasol Personal")

    selected_page_name = st.sidebar.radio(
        "Navigation",
        list(NAVIGATION_PAGES.keys()),
        index=0,
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Platform Architecture**\n"
        "- **Database:** Exasol Personal (In-Memory)\n"
        "- **Compute:** In-DB Python UDFs & SQL\n"
        "- **Metric:** Regret Score (Rupees at risk)\n"
        "- **License:** MIT Open Source"
    )

    page_fn = NAVIGATION_PAGES[selected_page_name]
    page_fn()


if __name__ == "__main__":
    main()
