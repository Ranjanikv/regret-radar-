"""Check Exasol Personal deployment status, connect via pyexasol, and initialize schema."""

import os
import shutil
import ssl
import subprocess
import sys
from typing import Any

import pyexasol
from dotenv import load_dotenv


def check_deployment_running() -> bool:
    """Check if an Exasol Personal deployment is running via the exasol CLI."""
    exasol_bin = shutil.which("exasol")
    if not exasol_bin:
        print("[WARN] 'exasol' CLI not on PATH. Proceeding to direct database connection test.")
        return False

    try:
        result = subprocess.run(
            [exasol_bin, "deployments", "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip()
        if "status=database_ready" in output or "running" in output:
            print(f"[OK] Exasol deployment detected running: {output}")
            return True

        # Fallback check via exasol info
        info_res = subprocess.run(
            [exasol_bin, "info"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Deployment State: running" in info_res.stdout:
            print("[OK] Exasol deployment is running (via exasol info).")
            return True

        print(f"[WARN] Deployment may not be ready. CLI output: {output or info_res.stdout}")
        return False
    except Exception as exc:
        print(f"[WARN] Unable to determine deployment status via CLI: {exc}")
        return False


def get_connection_config() -> dict[str, Any]:
    """Load Exasol connection credentials and settings from .env file."""
    load_dotenv()
    host = os.getenv("EXASOL_HOST", "127.0.0.1")
    port = os.getenv("PORT", "8563")
    user = os.getenv("USER", "sys")
    password = os.getenv("PASSWORD")

    if not password:
        raise ValueError(
            "PASSWORD is not set in .env. Please define EXASOL_HOST, PORT, USER, PASSWORD."
        )

    return {
        "dsn": f"{host}:{port}",
        "user": user,
        "password": password,
        "encryption": True,
        "websocket_sslopt": {"cert_reqs": ssl.CERT_NONE},
    }


def connect_exasol(config: dict[str, Any]) -> pyexasol.ExaConnection:
    """Establish a connection to Exasol database using pyexasol."""
    return pyexasol.connect(
        dsn=config["dsn"],
        user=config["user"],
        password=config["password"],
        encryption=config.get("encryption", True),
        websocket_sslopt=config.get("websocket_sslopt", {"cert_reqs": ssl.CERT_NONE}),
    )


def init_schema(conn: pyexasol.ExaConnection, schema_name: str = "REGRET_RADAR") -> None:
    """Create schema if it does not exist and set it as active."""
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
    conn.execute(f"OPEN SCHEMA {schema_name};")
    print(f"[OK] Schema '{schema_name}' verified / opened.")


def run_check() -> str:
    """Run full check: verify deployment, connect, init schema, and return DB version."""
    check_deployment_running()
    config = get_connection_config()
    print(f"Connecting to Exasol at {config['dsn']} as user '{config['user']}'...")
    with connect_exasol(config) as conn:
        db_version = str(conn.exasol_db_version)
        print(f"[OK] Connected successfully! Exasol Database Version: {db_version}")
        init_schema(conn, "REGRET_RADAR")
        return db_version


def main() -> None:
    """Entry point for command-line execution."""
    try:
        version = run_check()
        print(f"\nAll checks passed. Exasol version: {version}")
    except Exception as exc:
        print(f"\n[ERROR] Connection or initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
