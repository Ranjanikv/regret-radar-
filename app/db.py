"""Database connection and query utilities for Regret Radar."""

import os
import ssl
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import pyexasol
import streamlit as st
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def load_db_config() -> Dict[str, Any]:
    """Load Exasol connection credentials and settings from environment or .env file."""
    load_dotenv()
    host = os.getenv("EXASOL_HOST", "127.0.0.1")
    port = int(os.getenv("PORT") or os.getenv("EXASOL_PORT") or "8563")
    user = os.getenv("USER") or os.getenv("EXASOL_USER") or "SYS"
    pwd = os.getenv("PASSWORD") or os.getenv("EXASOL_PASSWORD") or "exasol"
    return {
        "dsn": f"{host}:{port}",
        "user": user,
        "password": pwd,
        "compression": True,
        "encryption": True,
        "websocket_sslopt": {"cert_reqs": ssl.CERT_NONE},
    }


def get_connection() -> pyexasol.ExaConnection:
    """Return a fresh, unshared pyexasol connection to avoid concurrency conflicts."""
    cfg = load_db_config()
    con = pyexasol.connect(
        dsn=cfg["dsn"],
        user=cfg["user"],
        password=cfg["password"],
        compression=cfg["compression"],
        encryption=cfg["encryption"],
        websocket_sslopt=cfg["websocket_sslopt"],
    )
    try:
        con.execute("OPEN SCHEMA REGRET_RADAR")
    except Exception as exc:
        st.warning(f"Failed to open schema REGRET_RADAR: {exc}")
    return con


def run_query(sql: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Execute a read query and return a pandas DataFrame, closing connection safely."""
    try:
        import app.main as app_main
    except ImportError:
        import main as app_main

    con = app_main.get_connection()
    if params is None:
        params = {}
    try:
        df = con.export_to_pandas(sql, query_params=params)
        df.columns = [c.lower() for c in df.columns]
        return df
    except pyexasol.exceptions.ExaQueryError as eq_err:
        raise RuntimeError(f"Database query error: {eq_err.message}") from eq_err
    except pyexasol.exceptions.ExaError as exa_err:
        raise RuntimeError(f"Exasol connection/execution error: {exa_err}") from exa_err
    except Exception as exc:
        raise RuntimeError(f"SQL execution failed: {exc}") from exc
    finally:
        try:
            con.close()
        except Exception:
            pass


def execute_dml(sql: str, params: Optional[Dict[str, Any]] = None) -> None:
    """Execute a DDL or DML statement safely."""
    try:
        import app.main as app_main
    except ImportError:
        import main as app_main

    con = app_main.get_connection()
    if params is None:
        params = {}
    try:
        con.execute(sql, query_params=params)
    finally:
        try:
            con.close()
        except Exception:
            pass


def fmt_rupee(value: Any) -> str:
    """Format numeric values as Indian Rupees (INR) with proper comma grouping."""
    if value is None or pd.isna(value):
        return "₹0.00"
    try:
        val_float = float(value)
        return f"₹{val_float:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"
