"""Tests for scripts/validate_connector.py.

By default these tests run with `--semantic-only` so they don't depend on
network access to the live schema host. There is one explicit Layer-1
network test that fetches the real schema; it is marked so CI can skip
it offline.

Run all: `pytest tests/connector_validator/`
Run offline only: `pytest tests/connector_validator/ -m "not network"`
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
EXAMPLES_GLOB = list(REPO_ROOT.glob("skills/connector-spec-*/examples/*.example.json"))
SCHEMA_URL = "https://schemas.analitiq.work/connector/latest.json"


def run_validator(document_path: Path, *extra: str, schema_url: str = SCHEMA_URL) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema-url", schema_url, "--document", str(document_path), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    return json.loads(proc.stdout)


def errors_of(result: dict, validator_id: str) -> list[dict]:
    return [f for f in result["findings"] if f["validator"] == validator_id and f["severity"] == "error"]


def warnings_of(result: dict, validator_id: str) -> list[dict]:
    return [f for f in result["findings"] if f["validator"] == validator_id and f["severity"] == "warning"]


# ---------------------------------------------------------------------------
# Layer 1 — JSON Schema (network)
# ---------------------------------------------------------------------------


@pytest.mark.network
def test_layer1_valid_api_connector_passes_against_live_schema():
    """Single network test that exercises the schema fetch path.

    All other tests run with --semantic-only and are offline-safe.
    """
    result = run_validator(FIXTURES / "valid_api_connector.json")
    error_findings = [f for f in result["findings"] if f["severity"] == "error"]
    assert not error_findings, f"unexpected errors: {error_findings}"
    assert result["passed"] is True


def test_schema_fetch_failure_is_diagnosed():
    bad_url = "http://127.0.0.1:1/nonexistent.json"
    result = run_validator(FIXTURES / "valid_api_connector.json", schema_url=bad_url)
    fetch_errors = [f for f in result["findings"] if f["validator"] == "json-schema" and "fetch" in f["message"].lower()]
    assert fetch_errors, f"expected a schema-fetch finding; got {result['findings']}"
    assert result["passed"] is False


# ---------------------------------------------------------------------------
# Reference examples — integration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("example", EXAMPLES_GLOB, ids=lambda p: p.name)
def test_reference_example_passes_semantic_validation(example):
    """Every shipped reference example must pass semantic validation.

    Layer 1 (JSON Schema) is exercised at build time by the dev workflow
    against the live schema; this test stays offline-safe.
    """
    result = run_validator(example, "--semantic-only")
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"{example.name}: {errors}"


def test_examples_glob_is_non_empty():
    """Guard against the parametrize collapsing to zero cases silently."""
    assert len(EXAMPLES_GLOB) >= 10, f"expected ≥ 10 reference examples, found {len(EXAMPLES_GLOB)}"


# ---------------------------------------------------------------------------
# Layer 2 — semantic validators (offline)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["connector_id", "connector_schema_version", "created_at", "updated_at"])
def test_reserved_field_caught(tmp_path, field):
    base = json.loads((FIXTURES / "valid_api_connector.json").read_text())
    base[field] = "should-not-be-here" if field != "connector_schema_version" else 7
    doc_path = tmp_path / f"reserved_{field}.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "reserved-field")
    assert len(errs) == 1, f"expected exactly one reserved-field finding for '{field}', got {result['findings']}"
    assert errs[0]["path"] == f"/{field}"


def test_unknown_scope_caught():
    result = run_validator(FIXTURES / "invalid_unknown_scope.json", "--semantic-only")
    errs = errors_of(result, "expression-resolver")
    messages = " ".join(e["message"] for e in errs)
    assert "secret.api_key" in messages or "secret.api_key" in " ".join(str(e) for e in errs), \
        f"expected unknown-scope finding for 'secret.api_key' (typo); got: {messages}"
    assert "connection.bogus" in messages, f"expected unknown sub-scope 'connection.bogus' caught; got: {messages}"
    assert "session.token" in messages, f"expected template var 'session.token' caught; got: {messages}"
    assert "hmac_sign" in messages, f"expected unknown function 'hmac_sign' caught; got: {messages}"


def test_transport_ref_caught():
    result = run_validator(FIXTURES / "invalid_transport_ref.json", "--semantic-only")
    errs = errors_of(result, "transport-ref")
    paths = sorted(e["path"] for e in errs)
    # Both default_transport and the nested authorize.transport_ref should be flagged.
    assert "/default_transport" in paths, f"expected /default_transport finding; got {paths}"
    assert any("authorize" in p and p.endswith("transport_ref") for p in paths), \
        f"expected nested authorize.transport_ref finding; got {paths}"


def test_dsn_unbound_placeholder_caught():
    result = run_validator(FIXTURES / "invalid_dsn_unbound.json", "--semantic-only")
    errs = errors_of(result, "dsn-binding")
    unbound = sorted(
        ph
        for ph in ("password", "port", "database")
        if any(ph in e["message"] for e in errs)
    )
    # The fixture omits exactly these three placeholder bindings; assert all three.
    assert unbound == ["database", "password", "port"], \
        f"expected unbound={{'password','port','database'}}, got {unbound}; findings={errs}"


def test_auth_shape_oauth_cc_forbidden_authorize_caught():
    result = run_validator(FIXTURES / "invalid_auth_shape_oauth_cc.json", "--semantic-only")
    errs = errors_of(result, "auth-shape")
    paths = [e["path"] for e in errs]
    assert "/auth/token_exchange" in paths, f"expected missing-token_exchange finding; got {paths}"
    assert "/auth/authorize" in paths, f"expected forbidden-authorize finding; got {paths}"


def test_tls_consistency_caught():
    result = run_validator(FIXTURES / "invalid_tls_consistency.json", "--semantic-only")
    errs = errors_of(result, "tls-consistency")
    assert errs, f"expected a tls-consistency finding; got {result['findings']}"
    assert any("ssl_ca_certificate" in e["message"] for e in errs)


def test_phase_resolvability_caught():
    result = run_validator(FIXTURES / "invalid_phase_resolvability.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert errs, f"expected a phase-resolvability finding; got {result['findings']}"
    assert any("tenant_id" in e["message"] for e in errs)
    # Importantly: paths must NOT contain the spurious '/t/' segment that
    # used to appear in the pre-fix implementation.
    assert not any("/t/" in e["path"] for e in errs), f"finding path leaked '/t/' wrapper: {errs}"


def test_type_map_coverage_warns_on_empty_rules():
    result = run_validator(FIXTURES / "invalid_type_map_empty_rules.json", "--semantic-only")
    warns = warnings_of(result, "type-map-coverage")
    assert warns, f"expected a type-map-coverage warning for empty rules; got {result['findings']}"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_malformed_json_diagnosed(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"kind":')
    result = run_validator(bad, "--semantic-only")
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert errs, f"expected a json-schema finding for malformed JSON; got {result['findings']}"
    assert result["passed"] is False


def test_missing_document_path_diagnosed(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    result = run_validator(missing, "--semantic-only")
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert errs, f"expected a json-schema finding for missing path; got {result['findings']}"
    assert result["passed"] is False


def test_semantic_and_json_only_are_mutually_exclusive(tmp_path):
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--schema-url", SCHEMA_URL,
            "--document", str(FIXTURES / "valid_api_connector.json"),
            "--semantic-only", "--json-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "mutually exclusive" in proc.stderr


def test_multiple_validators_all_fire(tmp_path):
    """A doc that triggers reserved-field AND auth-shape should report both."""
    base = json.loads((FIXTURES / "invalid_auth_shape_oauth_cc.json").read_text())
    base["connector_id"] = "should-not-be-here"
    doc_path = tmp_path / "multi.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    ids = {f["validator"] for f in result["findings"] if f["severity"] == "error"}
    assert {"reserved-field", "auth-shape"}.issubset(ids), f"expected both validator ids; got {ids}"
