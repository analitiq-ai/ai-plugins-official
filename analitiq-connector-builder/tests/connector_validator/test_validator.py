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
SCHEMA_URL = "https://schemas.analitiq.ai/connector/latest.json"


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


@pytest.mark.parametrize("field", ["connector_id", "created_at", "updated_at"])
def test_reserved_field_caught(tmp_path, field):
    base = json.loads((FIXTURES / "valid_api_connector.json").read_text())
    base[field] = "should-not-be-here"
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


def test_runtime_oauth_in_refresh_caught():
    result = run_validator(FIXTURES / "invalid_phase_runtime_oauth_in_refresh.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("auth.refresh" in e["message"].lower() or "/auth/refresh" in e["path"] for e in errs), \
        f"expected runtime.oauth.* in auth.refresh to be caught; got {errs}"


def test_oauth_runtime_on_non_oauth_connector_caught():
    result = run_validator(FIXTURES / "invalid_phase_oauth_runtime_on_apikey.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("oauth2_authorization_code" in e["message"] for e in errs), \
        f"expected oauth-only-on-oauth-connector finding; got {errs}"


def test_unknown_runtime_key_caught():
    result = run_validator(FIXTURES / "invalid_phase_unknown_runtime.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("bogus_key" in e["message"] or "closed set" in e["message"] for e in errs), \
        f"expected unknown runtime key finding; got {errs}"


def test_undeclared_connection_input_caught():
    result = run_validator(FIXTURES / "invalid_phase_undeclared_input.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("connection.parameters.region" in e["message"] for e in errs), \
        f"expected undeclared input finding; got {errs}"


def test_post_auth_input_referenced_in_auth_caught():
    """connection.parameters.tenant_id is phase=post_auth; auth.authorize is phase=auth.

    The validator must flag the cross-phase reference because the input
    isn't yet collected when authorize fires.
    """
    result = run_validator(FIXTURES / "invalid_phase_auth_input_in_authorize.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("tenant_id" in e["message"] and "auth" in e["message"] for e in errs), \
        f"expected cross-phase finding for tenant_id in auth.authorize; got {errs}"


def test_type_map_coverage_warns_on_empty_rules():
    result = run_validator(FIXTURES / "invalid_type_map_empty_rules.json", "--semantic-only")
    warns = warnings_of(result, "type-map-coverage")
    assert warns, f"expected a type-map-coverage warning for empty rules; got {result['findings']}"


def test_api_endpoint_coverage_passes_when_all_natives_covered():
    """API connector with type_maps covering every (type, format) pair from sibling endpoints."""
    result = run_validator(
        FIXTURES / "api_endpoints_covered" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    assert not errs, f"expected no coverage errors when fully covered; got {errs}"


def test_oauth_code_in_authorize_caught():
    """runtime.oauth.code is only available in auth.token_exchange, not authorize."""
    result = run_validator(FIXTURES / "invalid_phase_oauth_code_in_authorize.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("runtime.oauth.code" in e["message"] and "token_exchange" in e["message"] for e in errs), \
        f"expected oauth.code-in-authorize finding; got {errs}"


def test_stream_scope_in_auth_phase_caught():
    """stream.* is only available in the active phase; auth.authorize is at auth phase."""
    result = run_validator(FIXTURES / "invalid_phase_stream_in_authorize.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("stream" in e["message"].lower() and "active" in e["message"] for e in errs), \
        f"expected stream-only-in-active finding; got {errs}"


def test_auth_scope_in_pre_post_auth_phase_caught():
    """auth.* is only available from post_auth onward; auth.authorize runs at auth phase."""
    result = run_validator(FIXTURES / "invalid_phase_auth_in_authorize.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("auth.*" in e["message"] and "post_auth" in e["message"] for e in errs), \
        f"expected auth-scope-not-before-post_auth finding; got {errs}"


def test_pagination_outside_operation_caught():
    """runtime.pagination.* is operation-local; connector-level transport refs to it must error."""
    result = run_validator(FIXTURES / "invalid_phase_pagination_outside_op.json", "--semantic-only")
    errs = errors_of(result, "phase-resolvability")
    assert any("operation-local" in e["message"] for e in errs), \
        f"expected operation-local pagination finding; got {errs}"


def test_malformed_post_auth_outputs_warned():
    """post_auth_outputs entries with bad value_path should produce warnings."""
    result = run_validator(FIXTURES / "invalid_post_auth_outputs_malformed.json", "--semantic-only")
    warns = warnings_of(result, "phase-resolvability")
    assert any("value_path" in w["message"] for w in warns), \
        f"expected malformed-value_path warning; got {warns}"


def test_api_endpoint_coverage_walks_combiners_and_array_items():
    """oneOf/anyOf/allOf and tuple-style items[] must be recursed into."""
    result = run_validator(
        FIXTURES / "api_endpoints_combiners" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    # The endpoint declares ipv6 (oneOf branch), email + uri (items as list).
    # The connector only covers string + integer, so all three formats must be flagged.
    assert "'ipv6'" in messages, f"expected ipv6 from oneOf to be flagged; got {messages}"
    assert "'email'" in messages, f"expected email from items[0] to be flagged; got {messages}"
    assert "'uri'" in messages, f"expected uri from items[1] to be flagged; got {messages}"


def test_api_endpoint_coverage_flags_uncovered_natives():
    """API connector missing rules for natives present in sibling endpoints."""
    result = run_validator(
        FIXTURES / "api_endpoints_uncovered" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    # The uncovered fixture's endpoint references uuid, boolean, date-time —
    # the connector only declares string + integer.
    assert "'uuid'" in messages, f"expected uncovered 'uuid' to be flagged; got {errs}"
    assert "'boolean'" in messages, f"expected uncovered 'boolean' to be flagged; got {errs}"
    assert "'date-time'" in messages, f"expected uncovered 'date-time' to be flagged; got {errs}"


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
