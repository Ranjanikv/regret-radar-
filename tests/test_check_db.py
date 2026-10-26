"""Unit tests for Exasol deployment check and connection module."""

from unittest.mock import MagicMock, patch

import pytest

from load.check_db import (
    check_deployment_running,
    get_connection_config,
    init_schema,
    run_check,
)


def test_get_connection_config_missing_password(monkeypatch):
    """Test ValueError raised if PASSWORD is missing."""
    monkeypatch.delenv("PASSWORD", raising=False)
    with patch("load.check_db.load_dotenv"):
        with pytest.raises(ValueError, match="PASSWORD is not set"):
            get_connection_config()


def test_get_connection_config_success(monkeypatch):
    """Test proper config dictionary populated from environment."""
    monkeypatch.setenv("EXASOL_HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "8563")
    monkeypatch.setenv("USER", "sys")
    monkeypatch.setenv("PASSWORD", "secret")

    config = get_connection_config()
    assert config["dsn"] == "127.0.0.1:8563"
    assert config["user"] == "sys"
    assert config["password"] == "secret"
    assert config["encryption"] is True


@patch("load.check_db.shutil.which")
def test_check_deployment_running_no_cli(mock_which):
    """Test check_deployment_running handles missing exasol CLI cleanly."""
    mock_which.return_value = None
    assert check_deployment_running() is False


@patch("load.check_db.shutil.which", return_value="exasol")
@patch("load.check_db.subprocess.run")
def test_check_deployment_running_success(mock_run, mock_which):
    """Test check_deployment_running detects database_ready output."""
    mock_run.return_value = MagicMock(
        stdout="default status=database_ready preset=local/local",
        returncode=0,
    )
    assert check_deployment_running() is True


def test_init_schema():
    """Test init_schema executes correct DDL and opens schema."""
    mock_conn = MagicMock()
    init_schema(mock_conn, "REGRET_RADAR")
    mock_conn.execute.assert_any_call("CREATE SCHEMA IF NOT EXISTS REGRET_RADAR;")
    mock_conn.execute.assert_any_call("OPEN SCHEMA REGRET_RADAR;")


@patch("load.check_db.check_deployment_running", return_value=True)
@patch("load.check_db.get_connection_config")
@patch("load.check_db.connect_exasol")
@patch("load.check_db.init_schema")
def test_run_check(mock_init_schema, mock_connect, mock_config, mock_check_dept):
    """Test complete run_check pipeline."""
    mock_config.return_value = {
        "dsn": "localhost:8563",
        "user": "sys",
        "password": "pwd",
    }
    mock_conn = MagicMock()
    mock_conn.exasol_db_version = "2026.2.0"
    mock_connect.return_value.__enter__.return_value = mock_conn

    version = run_check()
    assert version == "2026.2.0"
    mock_init_schema.assert_called_once_with(mock_conn, "REGRET_RADAR")
