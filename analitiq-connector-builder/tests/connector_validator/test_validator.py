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
VALID_API_CONNECTOR = FIXTURES / "valid_api_connector" / "connector.json"
EXAMPLES_GLOB = list(REPO_ROOT.glob("skills/connector-spec-*/examples/*/*.example.json"))
SCHEMA_URL = "https://schemas.analitiq.ai/connector/latest.json"
TYPE_MAP_SCHEMA_URL = "https://schemas.analitiq.ai/type-map/latest.json"


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
    result = run_validator(VALID_API_CONNECTOR)
    error_findings = [f for f in result["findings"] if f["severity"] == "error"]
    assert not error_findings, f"unexpected errors: {error_findings}"
    assert result["passed"] is True


def test_schema_fetch_failure_is_diagnosed():
    bad_url = "http://127.0.0.1:1/nonexistent.json"
    result = run_validator(VALID_API_CONNECTOR, schema_url=bad_url)
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


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_reserved_field_caught(tmp_path, field):
    base = json.loads((VALID_API_CONNECTOR).read_text())
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


def test_type_map_missing_sibling_caught(tmp_path):
    """A connector with no sibling type-map.json triggers a coverage error."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("type-map.json" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-sibling finding; got {errs}"


def test_type_map_empty_array_caught(tmp_path):
    """A sibling type-map.json that is an empty array triggers a coverage error."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map.json").write_text("[]")
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("non-empty" in e["message"] for e in errs), \
        f"expected non-empty finding; got {errs}"


def test_api_endpoint_coverage_passes_when_all_natives_covered():
    """API connector with sibling type-map.json covering every (native_type, arrow_type) pair."""
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
    # The sibling type-map only covers string + integer, so the three rare natives must be flagged.
    assert "'ipv6'" in messages, f"expected ipv6 from oneOf to be flagged; got {messages}"
    assert "'email'" in messages, f"expected email from items[0] to be flagged; got {messages}"
    assert "'uri'" in messages, f"expected uri from items[1] to be flagged; got {messages}"


def test_api_endpoint_coverage_flags_uncovered_natives():
    """API connector with sibling type-map.json missing rules for endpoint natives."""
    result = run_validator(
        FIXTURES / "api_endpoints_uncovered" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    # The sibling type-map covers string + integer but the endpoint references uuid, boolean, date-time.
    assert "'uuid'" in messages, f"expected uncovered 'uuid' to be flagged; got {errs}"
    assert "'boolean'" in messages, f"expected uncovered 'boolean' to be flagged; got {errs}"
    assert "'date-time'" in messages, f"expected uncovered 'date-time' to be flagged; got {errs}"


def test_db_connector_missing_sibling_type_map_caught(tmp_path):
    """The missing-sibling check must fire for kind=database too, not just api."""
    base = json.loads((FIXTURES / "valid_db_connector" / "connector.json").read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("type-map.json" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-sibling finding for DB connector; got {errs}"


def test_db_connector_with_sibling_type_map_passes():
    """Happy path for DB connectors — non-empty sibling type-map, no endpoints/ required."""
    result = run_validator(
        FIXTURES / "valid_db_connector" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    assert not errs, f"expected DB connector with sibling type-map to pass; got {errs}"


def test_api_connector_missing_endpoints_dir_caught():
    """An API connector with no sibling endpoints/ dir is now a hard error."""
    result = run_validator(
        FIXTURES / "api_connector_no_endpoints" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    assert any("endpoints/" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-endpoints finding; got {errs}"


def test_api_connector_asymmetric_native_arrow_pair_caught():
    """A field declaring only one of native_type / arrow_type is a contract violation."""
    result = run_validator(
        FIXTURES / "api_connector_asymmetric_pair" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    msgs = " ".join(e["message"] for e in errs)
    assert "exactly one of native_type" in msgs, \
        f"expected asymmetric-pair finding; got {errs}"


def test_unknown_kind_skipped_silently(tmp_path):
    """Storage kinds (file/s3/stdout) are accepted by the schema but type-map is
    not yet defined for them; coverage should no-op without crashing."""
    base = json.loads((VALID_API_CONNECTOR).read_text())
    base["kind"] = "file"
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    cov = [f for f in result["findings"] if f["validator"] == "type-map-coverage"]
    assert not cov, f"unsupported kind should produce no type-map-coverage findings; got {cov}"


def test_arrow_narrowing_only_accepted_from_json_rule():
    """Object/List narrowings are valid ONLY when the rule resolves to Json."""
    result = run_validator(
        FIXTURES / "api_connector_arrow_narrowing_invalid" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    msgs = " ".join(e["message"] for e in errs)
    # Rule resolves uuid → Utf8 (not Json); endpoint declares Object → must be a mismatch error.
    assert "'Utf8'" in msgs and "'Object'" in msgs, \
        f"expected non-Json → Object narrowing to be flagged as mismatch; got {errs}"


def test_api_endpoint_arrow_mismatch_caught():
    """Endpoint arrow_type that disagrees with the sibling type-map's rendered canonical is an error."""
    result = run_validator(
        FIXTURES / "api_endpoints_arrow_mismatch" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    # id: native=uuid, arrow=Int64 vs type-map resolves uuid → Utf8 → mismatch
    assert "'Utf8'" in messages and "'Int64'" in messages, \
        f"expected uuid/Utf8 vs Int64 mismatch finding; got {errs}"
    # metadata: native=json, arrow=Object; type-map resolves json → Json; narrowing OK.
    # That site must NOT appear as an error.
    assert "'Object'" not in messages, \
        f"narrowing Json → Object should not be flagged; got {errs}"


def test_api_endpoint_arrow_template_substitution_renders():
    """A regex rule with ${name} substitution renders before comparison."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        connector = json.loads(VALID_API_CONNECTOR.read_text())
        (td / "connector.json").write_text(json.dumps(connector))
        (td / "type-map.json").write_text(json.dumps([
            {
                "match": "regex",
                "native": "^numeric\\((?<precision>[0-9]+),(?<scale>[0-9]+)\\)$",
                "canonical": "Decimal128(${precision}, ${scale})",
            }
        ]))
        (td / "endpoints").mkdir()
        (td / "endpoints" / "items.json").write_text(json.dumps({
            "$schema": "https://schemas.analitiq.ai/api-endpoint/latest.json",
            "endpoint_id": "items",
            "operations": {
                "read": {
                    "request": {"method": "GET", "path": "/items"},
                    "response": {
                        "records": {"ref": "response.body"},
                        "schema": {
                            "type": "object",
                            "properties": {
                                "amount": {
                                    "type": "string",
                                    "native_type": "numeric(10,2)",
                                    "arrow_type": "Decimal128(10, 2)",
                                }
                            },
                        },
                    },
                }
            },
        }))
        result = run_validator(td / "connector.json", "--semantic-only")
        errs = errors_of(result, "type-map-coverage")
        assert not errs, f"expected templated canonical to render and match; got {errs}"


def test_api_endpoint_write_coverage_passes_when_input_and_params_covered():
    """API connector with write-side input.schema + params natives fully covered by the sibling type-map.json."""
    result = run_validator(
        FIXTURES / "api_endpoints_write_covered" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    assert not errs, f"expected no coverage errors when write fully covered; got {errs}"


def test_api_endpoint_write_coverage_flags_uncovered_input_and_params():
    """Write-side natives in operations.write.<mode>.input.schema and .params must be walked."""
    result = run_validator(
        FIXTURES / "api_endpoints_write_uncovered" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    assert "'uuid'" in messages, f"expected uncovered write input 'uuid' to be flagged; got {errs}"
    assert "'date-time'" in messages, f"expected uncovered write input 'date-time' to be flagged; got {errs}"
    assert "'boolean'" in messages, f"expected uncovered write param 'boolean' to be flagged; got {errs}"
    # JSON pointers must locate the natives under the mode-keyed write path,
    # not at the bare operations/write level — guards against the walker
    # dropping the <mode> layer.
    assert "/operations/write/insert/input/schema" in messages, \
        f"expected /operations/write/insert/input/schema in pointers; got {messages}"
    assert "/operations/write/insert/params/" in messages, \
        f"expected /operations/write/insert/params/ in pointers; got {messages}"


def test_api_endpoint_write_coverage_walks_all_modes():
    """Both insert and upsert modes must be walked — guards the per-mode loop."""
    result = run_validator(
        FIXTURES / "api_endpoints_write_multimode" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    messages = " ".join(e["message"] for e in errs)
    # insert.input.schema declares uuid; upsert.input.schema declares date-time.
    # A regression that hardcoded only one mode would fail one of these.
    assert "'uuid'" in messages, f"expected insert-mode 'uuid' to be flagged; got {errs}"
    assert "'date-time'" in messages, f"expected upsert-mode 'date-time' to be flagged; got {errs}"
    assert "/operations/write/insert/input/schema" in messages, \
        f"expected insert pointer; got {messages}"
    assert "/operations/write/upsert/input/schema" in messages, \
        f"expected upsert pointer; got {messages}"


# ---------------------------------------------------------------------------
# type-map.json self-validation
# ---------------------------------------------------------------------------


def test_type_map_exact_rule_with_template_caught():
    result = run_validator(
        FIXTURES / "invalid_type_map_exact_with_template.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("exact" in e["message"] and "${" in e["message"] for e in errs), \
        f"expected exact-with-template finding; got {errs}"


def test_type_map_regex_missing_capture_caught():
    result = run_validator(
        FIXTURES / "invalid_type_map_regex_missing_capture.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("precision" in e["message"] and "capture" in e["message"] for e in errs), \
        f"expected missing-capture finding; got {errs}"


def test_type_map_duplicate_rule_warned():
    result = run_validator(
        FIXTURES / "invalid_type_map_duplicate.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    warns = warnings_of(result, "type-map-rule")
    assert any("duplicate" in w["message"] and "BIGINT" in w["message"] for w in warns), \
        f"expected duplicate-rule warning; got {warns}"


def test_to_python_regex_passthroughs():
    """Direct unit test of the ECMA→Python translator's pass-through contract."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("vc", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # ECMA named groups rewritten:
    assert mod._to_python_regex(r"^(?<n>\d+)$") == r"^(?P<n>\d+)$"
    # Anonymous groups untouched:
    assert mod._to_python_regex(r"^(\d+)$") == r"^(\d+)$"
    # Non-capturing untouched:
    assert mod._to_python_regex(r"^(?:foo|bar)$") == r"^(?:foo|bar)$"
    # Mixed: ECMA rewritten, anonymous left alone:
    assert mod._to_python_regex(r"^(?<a>\d+)-(\d+)$") == r"^(?P<a>\d+)-(\d+)$"


def test_malformed_sibling_type_map_caught(tmp_path):
    """A sibling type-map.json that's syntactically broken JSON must raise a hard error."""
    base = json.loads((VALID_API_CONNECTOR).read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map.json").write_text("{")
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("could not be read or parsed" in e["message"] for e in errs), \
        f"expected JSON-decode error for malformed sibling; got {errs}"


def test_lambda_handles_empty_capture(tmp_path):
    """An empty-capture match must render as empty string (not leak the literal ${name})."""
    base = json.loads((VALID_API_CONNECTOR).read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map.json").write_text(json.dumps([
        {
            "match": "regex",
            "native": "^optional_(?<size>[0-9]*)$",
            "canonical": "FixedSizeBinary(${size})",
        }
    ]))
    (tmp_path / "endpoints").mkdir()
    (tmp_path / "endpoints" / "items.json").write_text(json.dumps({
        "$schema": "https://schemas.analitiq.ai/api-endpoint/latest.json",
        "endpoint_id": "items",
        "operations": {
            "read": {
                "request": {"method": "GET", "path": "/items"},
                "response": {
                    "records": {"ref": "response.body"},
                    "schema": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "string", "native_type": "optional_", "arrow_type": "FixedSizeBinary()"}
                        }
                    }
                }
            }
        }
    }))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    # The rendered canonical should be `FixedSizeBinary()` (empty capture → ""),
    # which matches the endpoint's arrow_type. The literal `${size}` must not leak.
    assert not any("${size}" in e["message"] for e in errs), \
        f"empty capture leaked ${{size}} literal into rendered canonical; got {errs}"


def test_adbc_example_shape_invariants():
    """Pin ADBC contract distinguishing properties so a regression that re-adds
    `tls` or uses a non-enum `driver` is caught — Layer 1 already rejects these,
    but the example is canonical and worth defending here too."""
    ex = json.loads((REPO_ROOT / "skills" / "connector-spec-db" / "examples" /
                     "postgresql-adbc" / "postgresql-adbc.example.json").read_text())
    transport = ex["transports"]["database"]
    assert transport["transport_type"] == "adbc"
    assert transport["driver"] in ("postgresql", "snowflake", "bigquery"), \
        f"driver must be in the closed enum; got {transport['driver']!r}"
    assert "tls" not in transport, "ADBC transport must not declare a tls block"
    assert "db_kwargs" in transport or "dsn" in transport, \
        "AdbcTransport requires at least one of dsn / db_kwargs"


def test_valid_type_map_passes_semantic():
    result = run_validator(
        FIXTURES / "valid_type_map.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert not errs, f"expected no errors on valid type-map; got {errs}"


def test_type_map_python_named_group_caught():
    """ECMA-262 is the contract; (?P<name>...) Python declaration syntax must be rejected."""
    result = run_validator(
        FIXTURES / "invalid_type_map_python_syntax.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("Python-only" in e["message"] for e in errs), \
        f"expected Python-syntax finding; got {errs}"


def test_type_map_broken_regex_caught_without_template():
    """A regex rule with a malformed native must be flagged even when canonical has no ${...}."""
    result = run_validator(
        FIXTURES / "invalid_type_map_broken_regex.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] and e["path"] == "/0/native" for e in errs), \
        f"expected broken-regex finding on rule 0; got {errs}"


def test_type_map_python_backreference_caught():
    """Python-only `(?P=name)` backreferences must also be rejected."""
    result = run_validator(
        FIXTURES / "invalid_type_map_python_backref.json",
        "--semantic-only",
        schema_url=TYPE_MAP_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("Python-only" in e["message"] for e in errs), \
        f"expected Python-syntax finding for backref; got {errs}"


def test_unhashable_rule_value_does_not_crash(tmp_path):
    """A `match`/`native` that isn't a primitive must not crash the dedupe set."""
    tm = tmp_path / "type-map.json"
    tm.write_text(json.dumps([
        {"match": ["regex"], "native": "x", "canonical": "Utf8"},
        {"match": "exact", "native": "BIGINT", "canonical": "Int64"}
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_SCHEMA_URL)
    # The validator must produce a structured result, not crash.
    assert "findings" in result, f"expected structured output, got {result}"


def test_is_type_map_doc_rejects_empty_list_in_semantic_only(tmp_path):
    """An empty type-map.json should not dispatch type-map-rule (Layer 1 owns minItems)."""
    tm = tmp_path / "type-map.json"
    tm.write_text("[]")
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_SCHEMA_URL)
    rule_findings = [f for f in result["findings"] if f["validator"] == "type-map-rule"]
    assert not rule_findings, f"empty type-map should not generate type-map-rule findings; got {rule_findings}"


def test_connector_validation_surfaces_sibling_rule_errors():
    """check_type_map_coverage must run rule checks on the sibling so a broken regex
    in type-map.json is caught when validating the connector, not only when invoked
    against the type-map directly."""
    result = run_validator(
        FIXTURES / "connector_with_broken_type_map" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] for e in errs), \
        f"expected broken sibling regex to surface via connector path; got {errs}"


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
            "--document", str(VALID_API_CONNECTOR),
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
    base["created_at"] = "should-not-be-here"
    doc_path = tmp_path / "multi.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    ids = {f["validator"] for f in result["findings"] if f["severity"] == "error"}
    assert {"reserved-field", "auth-shape"}.issubset(ids), f"expected both validator ids; got {ids}"
