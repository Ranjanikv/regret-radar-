"""Unit tests for Exasol bulk loader module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from load.load import apply_schema, bulk_load_all, detect_row_separator, load_table


def test_detect_row_separator():
    """Verify detection of CRLF vs LF line terminators."""
    with tempfile.TemporaryDirectory() as tmpdir:
        crlf_file = Path(tmpdir) / "crlf.csv"
        crlf_file.write_bytes(b"a,b\r\n1,2\r\n")
        assert detect_row_separator(crlf_file) == "CRLF"

        lf_file = Path(tmpdir) / "lf.csv"
        lf_file.write_bytes(b"a,b\n1,2\n")
        assert detect_row_separator(lf_file) == "LF"


def test_apply_schema():
    """Verify apply_schema splits SQL file and executes each statement."""
    mock_conn = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        sql_file = Path(tmpdir) / "test.sql"
        sql_file.write_text("CREATE SCHEMA T1; CREATE TABLE T2 (id INT);", encoding="utf-8")
        apply_schema(mock_conn, sql_file)
        assert mock_conn.execute.call_count == 2


def test_load_table():
    """Verify load_table truncates, imports via pyexasol, and fetches count."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchval.return_value = 42

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = Path(tmpdir) / "sample.csv"
        csv_file.write_bytes(b"id,val\r\n1,x\r\n")

        count, duration = load_table(mock_conn, "REGRET_RADAR", "sample", csv_file)
        assert count == 42
        assert duration >= 0.0
        mock_conn.execute.assert_any_call('TRUNCATE TABLE "REGRET_RADAR"."SAMPLE";')
        mock_conn.import_from_file.assert_called_once()


def test_bulk_load_all_missing_dir():
    """Verify bulk_load_all raises FileNotFoundError when data directory does not exist."""
    with pytest.raises(FileNotFoundError):
        bulk_load_all(Path("non_existent_folder_xyz"))
