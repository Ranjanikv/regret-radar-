[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet("setup", "data", "load", "score", "app", "test", "demo")]
    [string]$Target = "test"
)

$ErrorActionPreference = "Stop"
$python = "python"

switch ($Target) {
    "setup" {
        & $python -m pip install -r requirements.txt
    }
    "data" {
        & $python -m data_gen.generate --scale small
    }
    "load" {
        & $python -m load.bulk_load
    }
    "score" {
        & $python -m load.run_scoring
    }
    "app" {
        streamlit run app/main.py
    }
    "test" {
        ruff check .
        pytest
    }
    "demo" {
        & $python -m load.demo
    }
}
