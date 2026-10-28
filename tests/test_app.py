"""Unit tests for Streamlit application utility functions and query formatting."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.main import fmt_rupee, load_db_config, run_query


def test_fmt_rupee():
    """Verify rupee formatting with various numeric types and edge cases."""
    assert fmt_rupee(100) == "₹100.00"
    assert fmt_rupee(1234567.89) == "₹1,234,567.89"
    assert fmt_rupee(0) == "₹0.00"
    assert fmt_rupee(None) == "₹0.00"
    assert fmt_rupee(float("nan")) == "₹0.00"


def test_load_db_config():
    """Verify load_db_config reads connection variables correctly."""
    with patch.dict(
        "os.environ",
        {"EXASOL_HOST": "10.0.0.1", "PORT": "8563", "USER": "test_user", "PASSWORD": "secret"},
    ):
        cfg = load_db_config()
        assert cfg["dsn"] == "10.0.0.1:8563"
        assert cfg["user"] == "test_user"
        assert cfg["password"] == "secret"
        assert cfg["encryption"] is True


def test_run_query_no_params():
    """Verify run_query executes with no parameters passed."""
    mock_conn = MagicMock()
    mock_df = pd.DataFrame({"col": [1, 2]})
    mock_conn.export_to_pandas.return_value = mock_df

    with patch("app.main.get_connection", return_value=mock_conn):
        res = run_query("SELECT * FROM test_table")
        assert res.equals(mock_df)
        mock_conn.export_to_pandas.assert_called_once_with(
            "SELECT * FROM test_table", query_params={}
        )


def test_run_query_with_params():
    """Verify run_query passes query_params dictionary to pyexasol."""
    mock_conn = MagicMock()
    mock_df = pd.DataFrame({"customer_id": ["CUST_001"]})
    mock_conn.export_to_pandas.return_value = mock_df

    with patch("app.main.get_connection", return_value=mock_conn):
        params = {"cid": "CUST_001"}
        res = run_query("SELECT * FROM customers WHERE customer_id = {cid}", params=params)
        assert res.equals(mock_df)
        mock_conn.export_to_pandas.assert_called_once_with(
            "SELECT * FROM customers WHERE customer_id = {cid}", query_params=params
        )


def test_run_query_literal_brace_and_error_handling():
    """Verify run_query propagates Exasol exceptions with clear context."""
    mock_conn = MagicMock()
    mock_conn.export_to_pandas.side_effect = RuntimeError("Syntax error near WHERE")

    with patch("app.main.get_connection", return_value=mock_conn):
        with pytest.raises(RuntimeError, match="SQL execution failed: Syntax error near WHERE"):
            run_query("SELECT * FROM test WHERE col = 'literal_text'")
