"""Tests for scripts/validate_connector.py.

Run with: pytest tests/connector_validator/
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate_connector.py"
FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_URL = "https://schemas.analitiq.work/connector/latest.json"


def run_validator(document_path: Path, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema-url", SCHEMA_URL, "--document", str(document_path), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(proc.stdout)


def test_valid_api_connector_passes():
    result = run_validator(FIXTURES / "valid_api_connector.json")
    error_findings = [f for f in result["findings"] if f["severity"] == "error"]
    assert not error_findings, f"unexpected errors: {error_findings}"
    assert result["passed"] is True


def test_reserved_field_caught():
    result = run_validator(FIXTURES / "invalid_reserved_field.json", "--semantic-only")
    ids = {f["validator"] for f in result["findings"]}
    assert "reserved-field" in ids
    assert result["passed"] is False


def test_dsn_unbound_placeholder_caught():
    result = run_validator(FIXTURES / "invalid_dsn_unbound.json", "--semantic-only")
    findings = [f for f in result["findings"] if f["validator"] == "dsn-binding" and f["severity"] == "error"]
    assert findings, "expected at least one dsn-binding error"
    assert any("password" in f["message"] or "port" in f["message"] or "database" in f["message"] for f in findings)
