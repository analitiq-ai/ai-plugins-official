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
TYPE_MAP_READ_SCHEMA_URL = "https://schemas.analitiq.ai/type-map-read/latest.json"
TYPE_MAP_WRITE_SCHEMA_URL = "https://schemas.analitiq.ai/type-map-write/latest.json"

# Reference db packages ship a read map and a write map alongside the
# connector body. The network tests below exercise the Layer-1 schema-fetch
# path for both type-map directions against the live published schemas.
_DB_EXAMPLE_DIRS = sorted(
    d for d in (REPO_ROOT / "skills/connector-spec-db/examples").iterdir() if d.is_dir()
)
EXAMPLE_READ_MAPS = [d / "type-map-read.json" for d in _DB_EXAMPLE_DIRS if (d / "type-map-read.json").is_file()]
EXAMPLE_WRITE_MAPS = [d / "type-map-write.json" for d in _DB_EXAMPLE_DIRS if (d / "type-map-write.json").is_file()]


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


@pytest.mark.network
@pytest.mark.parametrize("read_map", EXAMPLE_READ_MAPS, ids=lambda p: p.parent.name)
def test_layer1_example_read_map_passes_against_live_schema(read_map):
    """Reference read maps must validate against the published
    type-map-read schema — full Layer 1 + Layer 2, no --semantic-only."""
    result = run_validator(read_map, schema_url=TYPE_MAP_READ_SCHEMA_URL)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"{read_map.parent.name} read map: {errors}"


@pytest.mark.network
@pytest.mark.parametrize("write_map", EXAMPLE_WRITE_MAPS, ids=lambda p: p.parent.name)
def test_layer1_example_write_map_passes_against_live_schema(write_map):
    """Reference write maps must validate against the published
    type-map-write schema. This is the direction that previously had no
    published schema and ran --semantic-only; it now gets full Layer 1."""
    result = run_validator(write_map, schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"{write_map.parent.name} write map: {errors}"


@pytest.mark.network
def test_layer1_malformed_write_map_rejected_against_live_schema(tmp_path):
    """The published write schema must actually constrain shape, not merely be
    fetchable — a malformed write map is rejected at Layer 1. Without this, the
    positive write-map test above could stay green against a no-op/over-permissive
    or mis-referenced schema."""
    bad = tmp_path / "type-map-write.json"
    # `match` outside the enum and `native` (the render side) missing.
    bad.write_text(json.dumps([{"match": "glob", "canonical": "Boolean"}]))
    result = run_validator(bad, schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    # A real schema rejection points into the document (e.g. "/0", "/0/match");
    # a schema-fetch failure carries the same validator id but an empty path.
    # Require a document-anchored error so a misconfigured fetch can't pass as
    # enforcement.
    schema_errors = [
        f for f in result["findings"]
        if f["validator"] == "json-schema" and f["path"].startswith("/")
    ]
    assert schema_errors, f"expected a Layer-1 schema rejection into the document; got {result['findings']}"
    assert result["passed"] is False


def test_db_example_maps_present():
    """Guard against the network parametrize collapsing to zero cases."""
    assert len(EXAMPLE_READ_MAPS) >= 3, f"expected ≥ 3 example read maps, found {EXAMPLE_READ_MAPS}"
    assert len(EXAMPLE_WRITE_MAPS) >= 3, f"expected ≥ 3 example write maps, found {EXAMPLE_WRITE_MAPS}"


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


def test_empty_template_variable_caught(tmp_path):
    """`${}` names no scope and resolves to nothing at runtime, so it must be
    flagged rather than slip through (the `[^}]*` regex fix in #48)."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["transports"]["api"]["headers"]["X-Empty"] = {"template": "Bearer ${}"}
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "expression-resolver")
    empty = [e for e in errs if "empty template variable" in e["message"]]
    assert len(empty) == 1, f"expected exactly one empty-template finding; got {result['findings']}"
    # The valid `${secrets.api_key}` template in the same doc must not be flagged.
    assert not any("secrets.api_key" in e["message"] for e in errs), \
        f"valid template var wrongly flagged; got {errs}"


def test_whitespace_template_variable_caught(tmp_path):
    """`${   }` is empty after stripping — reported as empty, not as an
    unknown scope (which would be a misleading message)."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["transports"]["api"]["headers"]["X-Blank"] = {"template": "Bearer ${   }"}
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "expression-resolver")
    assert any("empty template variable" in e["message"] for e in errs), \
        f"expected empty-template finding for '${{   }}'; got {result['findings']}"
    assert not any("unknown scope" in e["message"] for e in errs), \
        f"whitespace var should not be reported as unknown scope; got {errs}"


def test_unclosed_template_variable_caught(tmp_path):
    """A `${` with no closing `}` is not extracted, so it would survive as a
    literal at runtime — flag it. A legitimate template with literal JSON
    braces (`{ }` not preceded by `$`) must NOT trip this."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["transports"]["api"]["headers"]["X-Unclosed"] = {"template": "Bearer ${secrets.api_key"}
    base["transports"]["api"]["headers"]["X-Json"] = {"template": '{"key": "${secrets.api_key}"}'}
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "expression-resolver")
    unclosed = [e for e in errs if "unclosed template variable" in e["message"]]
    # Exactly one: the dangling `${`. The literal-brace JSON template is clean.
    assert len(unclosed) == 1, f"expected exactly one unclosed finding; got {result['findings']}"


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


def test_dsn_empty_placeholder_caught(tmp_path):
    """An empty `{}` in a DSN url_template names no binding and resolves to
    nothing at runtime — flagged rather than silently ignored (the `[^}]*`
    fix applied to the DSN `{placeholder}` markers, same bug class as `${}`)."""
    base = {
        "$schema": "https://schemas.analitiq.ai/connector/latest.json",
        "kind": "database",
        "connector_id": "fixture-dsn-empty",
        "version": "1.0.0",
        "default_transport": "db",
        "transports": {
            "db": {
                "transport_type": "sqlalchemy",
                "driver": "postgresql+asyncpg",
                "dsn": {
                    "kind": "url_template",
                    "template": "postgresql://{host}:{}/{database}",
                    "bindings": {
                        "host": {"value": {"ref": "connection.parameters.host"}, "encoding": "host"},
                        "database": {"value": {"ref": "connection.parameters.database"}, "encoding": "url_path_segment"},
                    },
                },
            }
        },
        "auth": {"type": "db"},
        "connection_contract": {
            "inputs": {
                "host": {"source": "user", "phase": "pre_auth", "storage": "connection.parameters", "type": "string", "required": True},
                "database": {"source": "user", "phase": "pre_auth", "storage": "connection.parameters", "type": "string", "required": True},
            }
        },
    }
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "dsn-binding")
    assert any(
        "empty placeholder" in e["message"] and e["path"] == "/transports/db/dsn/template"
        for e in errs
    ), f"expected empty-placeholder dsn-binding finding; got {errs}"
    # The valid `{host}`/`{database}` markers are bound, so the only dsn-binding
    # error is the empty one — not a generic 'no matching binding'.
    assert not any("has no matching binding" in e["message"] for e in errs), \
        f"valid bindings wrongly flagged as unbound; got {errs}"


def test_dsn_unclosed_brace_caught(tmp_path):
    """A `{` with no closing `}` in a DSN url_template is an unbalanced brace
    that corrupts the connection string — flagged rather than silently ignored.
    Braces are reserved for `{placeholder}` markers in a DSN, so any stray one
    is malformed."""
    base = {
        "$schema": "https://schemas.analitiq.ai/connector/latest.json",
        "kind": "database",
        "connector_id": "fixture-dsn-unclosed",
        "version": "1.0.0",
        "default_transport": "db",
        "transports": {
            "db": {
                "transport_type": "sqlalchemy",
                "driver": "postgresql+asyncpg",
                "dsn": {
                    "kind": "url_template",
                    "template": "postgresql://{host}/{database",
                    "bindings": {
                        "host": {"value": {"ref": "connection.parameters.host"}, "encoding": "host"},
                        "database": {"value": {"ref": "connection.parameters.database"}, "encoding": "url_path_segment"},
                    },
                },
            }
        },
        "auth": {"type": "db"},
        "connection_contract": {
            "inputs": {
                "host": {"source": "user", "phase": "pre_auth", "storage": "connection.parameters", "type": "string", "required": True},
                "database": {"source": "user", "phase": "pre_auth", "storage": "connection.parameters", "type": "string", "required": True},
            }
        },
    }
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "dsn-binding")
    assert any(
        "unbalanced or unclosed brace" in e["message"] and e["path"] == "/transports/db/dsn/template"
        for e in errs
    ), f"expected unclosed-brace dsn-binding finding; got {errs}"


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
    # Paths must NOT contain a spurious '/t/' segment — the walker must not
    # leak the iteration variable name as a JSON-pointer component.
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
    """A connector with no sibling type-map-read.json triggers a coverage error."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("type-map-read.json" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-sibling finding; got {errs}"


def test_type_map_empty_array_caught(tmp_path):
    """A sibling type-map-read.json that is an empty array triggers a coverage error."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text("[]")
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
    assert any("type-map-read.json" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-sibling finding for DB connector; got {errs}"


def test_db_connector_with_sibling_type_maps_passes():
    """Happy path for DB connectors — non-empty sibling read + write maps, no endpoints/ required."""
    result = run_validator(
        FIXTURES / "valid_db_connector" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    assert not errs, f"expected DB connector with sibling type maps to pass; got {errs}"
    # The fixture write map covers the full canonical vocabulary, so the
    # rule-8 probe must stay quiet too.
    warns = warnings_of(result, "type-map-write-coverage")
    assert not warns, f"expected no vocabulary-gap warnings; got {warns}"


def test_db_connector_missing_write_map_caught(tmp_path):
    """kind=database requires a sibling type-map-write.json; absence is an error."""
    base = json.loads((FIXTURES / "valid_db_connector" / "connector.json").read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(
        (FIXTURES / "valid_db_connector" / "type-map-read.json").read_text()
    )
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("type-map-write.json" in e["message"] and "missing" in e["message"] for e in errs), \
        f"expected missing-write-map finding for DB connector; got {errs}"


def test_legacy_type_map_filename_caught(tmp_path):
    """A pre-split sibling `type-map.json` must surface a rename pointer even
    when the new read map is also present — the stale file would otherwise
    linger unnoticed."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    src = FIXTURES / "valid_api_connector"
    (tmp_path / "type-map-read.json").write_text((src / "type-map-read.json").read_text())
    (tmp_path / "type-map.json").write_text((src / "type-map-read.json").read_text())
    (tmp_path / "endpoints").mkdir()
    (tmp_path / "endpoints" / "ping.json").write_text((src / "endpoints" / "ping.json").read_text())
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("legacy" in e["message"] and "type-map-read.json" in e["message"] for e in errs), \
        f"expected legacy-filename finding; got {errs}"


def test_api_connector_with_write_map_caught(tmp_path):
    """API connectors must not ship a write map — the write direction is a
    database-package concept."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    src = FIXTURES / "valid_api_connector"
    (tmp_path / "type-map-read.json").write_text((src / "type-map-read.json").read_text())
    (tmp_path / "type-map-write.json").write_text(json.dumps([
        {"match": "exact", "canonical": "Utf8", "native": "TEXT"}
    ]))
    (tmp_path / "endpoints").mkdir()
    (tmp_path / "endpoints" / "ping.json").write_text((src / "endpoints" / "ping.json").read_text())
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("must not ship" in e["message"] and "type-map-write.json" in e["message"] for e in errs), \
        f"expected api-with-write-map finding; got {errs}"


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
    """A field declaring only one of native_type / arrow_type is a contract
    violation. Exercises ALL FOUR walker sites (read.response.schema,
    read.params, write.<mode>.input.schema, write.<mode>.params) plus the
    'both keys present, non-string values' variant."""
    result = run_validator(
        FIXTURES / "api_connector_asymmetric_pair" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-coverage")
    msgs = " ".join(e["message"] for e in errs)
    # Asymmetric (exactly-one-of-pair) — one per site.
    assert "/operations/read/response/schema/properties/id" in msgs, \
        f"expected asymmetric finding from read.response.schema; got {msgs}"
    assert "/operations/read/params/q" in msgs, \
        f"expected asymmetric finding from read.params; got {msgs}"
    assert "/operations/write/insert/input/schema/properties/name" in msgs, \
        f"expected asymmetric finding from write.insert.input.schema; got {msgs}"
    assert "/operations/write/insert/params/tenant" in msgs, \
        f"expected asymmetric finding from write.insert.params; got {msgs}"
    # Non-string-both variant.
    assert any("non-string value(s)" in e["message"]
               and "/operations/read/response/schema/properties/raw" in e["message"]
               for e in errs), \
        f"expected non-string-both finding for /raw field; got {errs}"


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


def test_storage_kind_still_validates_sibling_type_map_rules(tmp_path):
    """Storage kinds (file/s3/stdout) have no per-kind coverage contract, but
    a sibling broken type-map-read.json must still surface — authors who ship
    a type map ahead of engine support shouldn't get a silent pass."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["kind"] = "file"
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(json.dumps([
        {"match": "regex", "native": "^BAD[REGEX", "canonical": "Utf8"}
    ]))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] for e in errs), \
        f"storage-kind sibling type-map must still be rule-checked; got {errs}"


def test_adbc_example_passes_semantic_validation():
    """End-to-end semantic check against the ADBC postgres example —
    distinct shape from the sqlalchemy postgres example, so it deserves its
    own pass. Pins that future validator changes don't accidentally flag
    ADBC's lack of `tls` block or its db_kwargs-with-value-expressions."""
    result = run_validator(
        REPO_ROOT / "skills" / "connector-spec-db" / "examples" /
        "postgresql-adbc" / "postgresql-adbc.example.json",
        "--semantic-only",
    )
    errs = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errs, f"ADBC example should pass semantic validation; got {errs}"


def test_connector_with_endpoints_and_broken_type_map_renders_skipped_rule():
    """End-to-end: broken regex in sibling type-map is reported by
    check_type_map_rules, AND _render_canonical's defensive 'except re.error:
    continue' is exercised when the endpoint walker calls it — proving the
    cross-validator wiring + the render-time fallback both stay correct."""
    result = run_validator(
        FIXTURES / "connector_with_broken_type_map" / "connector.json",
        "--semantic-only",
    )
    # Rule-level error from the cross-validator dispatch.
    rule_errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] for e in rule_errs), \
        f"expected broken-regex rule error; got {rule_errs}"
    # Coverage walker tried to resolve `varchar(255)` against the broken rule;
    # `_render_canonical` swallowed the re.error and returned None, surfacing
    # an unresolved-native error from check_type_map_coverage.
    cov_errs = errors_of(result, "type-map-coverage")
    assert any("no matching rule" in e["message"] and "varchar(255)" in e["message"]
               for e in cov_errs), \
        f"expected unresolved-native coverage error proving _render_canonical was reached; got {cov_errs}"


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
        # Pattern is authored UPPERCASE per the contract; the endpoint's
        # lowercase native must still resolve via the engine-mirroring
        # normalization (uppercase + whitespace-collapse) before matching.
        (td / "type-map-read.json").write_text(json.dumps([
            {
                "match": "regex",
                "native": "^NUMERIC\\((?<precision>[0-9]+),(?<scale>[0-9]+)\\)$",
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
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("exact" in e["message"] and "${" in e["message"] for e in errs), \
        f"expected exact-with-template finding; got {errs}"


def test_type_map_regex_missing_capture_caught():
    result = run_validator(
        FIXTURES / "invalid_type_map_regex_missing_capture.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("precision" in e["message"] and "capture" in e["message"] for e in errs), \
        f"expected missing-capture finding; got {errs}"


def test_type_map_empty_placeholder_caught(tmp_path):
    """An empty `${}` on a render value renders to nothing — flagged as a
    type-map-rule error rather than surviving into the output verbatim (the
    `_PLACEHOLDER_RE` `[^}]*` fix in #48)."""
    read_path = tmp_path / "type-map-read.json"
    read_path.write_text(json.dumps([
        {"match": "exact", "native": "BOOLEAN", "canonical": "Boolean${}"}
    ]))
    result = run_validator(read_path, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    assert any(
        e["path"] == "/0/canonical" and "empty" in e["message"] and "${}" in e["message"]
        for e in errs
    ), f"expected empty-placeholder finding on /0/canonical; got {errs}"


def test_type_map_regex_empty_placeholder_caught(tmp_path):
    """The load-bearing path: a `regex` write rule whose render value mixes a
    valid `${p}` with an empty `${}`. The empty-placeholder gate sits BEFORE
    the named-capture check, so the empty `${}` short-circuits with a precise
    error (not a misleading 'no matching capture group'), and the valid sibling
    capture neither masks it nor is itself wrongly flagged. Also exercises the
    write direction (render key = `native`), which the exact-rule test above
    does not."""
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps([
        {
            "match": "regex",
            "canonical": "^Decimal128\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
            "native": "NUMERIC(${p}, ${})",
        }
    ]))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    empty = [
        e for e in errs
        if e["path"] == "/0/native" and "empty" in e["message"] and "${}" in e["message"]
    ]
    assert len(empty) == 1, f"expected one empty-placeholder finding on /0/native; got {errs}"
    # The empty placeholder short-circuits the rule, so the valid `${p}` capture
    # is not reported as unbacked — no misleading 'capture' error.
    assert not any("capture" in e["message"] for e in errs), \
        f"valid capture wrongly flagged; got {errs}"


def test_type_map_unclosed_placeholder_caught(tmp_path):
    """A `${` with no closing `}` on a render value renders as a literal —
    flagged as a type-map-rule error (the #48 unclosed-brace fold-in)."""
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps([
        {"match": "regex", "canonical": "^Decimal128\\((?<p>\\d+)\\)$", "native": "NUMERIC(${p)"}
    ]))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    assert any(e["path"] == "/0/native" and "unclosed" in e["message"] for e in errs), \
        f"expected unclosed-placeholder finding on /0/native; got {errs}"


def test_type_map_duplicate_rule_warned():
    result = run_validator(
        FIXTURES / "invalid_type_map_duplicate.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
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
    """A sibling type-map-read.json that's syntactically broken JSON must raise a hard error."""
    base = json.loads((VALID_API_CONNECTOR).read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text("{")
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("could not be read or parsed" in e["message"] for e in errs), \
        f"expected JSON-decode error for malformed sibling; got {errs}"


def test_lambda_handles_empty_capture(tmp_path):
    """An empty-capture match must render as empty string (not leak the literal ${name})."""
    base = json.loads((VALID_API_CONNECTOR).read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(json.dumps([
        {
            "match": "regex",
            "native": "^OPTIONAL_(?<size>[0-9]*)$",
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
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert not errs, f"expected no errors on valid type-map; got {errs}"


def test_type_map_python_named_group_caught():
    """ECMA-262 is the contract; (?P<name>...) Python declaration syntax must be rejected."""
    result = run_validator(
        FIXTURES / "invalid_type_map_python_syntax.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("Python-only" in e["message"] for e in errs), \
        f"expected Python-syntax finding; got {errs}"


def test_type_map_broken_regex_caught_without_template():
    """A regex rule with a malformed native must be flagged even when canonical has no ${...}."""
    result = run_validator(
        FIXTURES / "invalid_type_map_broken_regex.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] and e["path"] == "/0/native" for e in errs), \
        f"expected broken-regex finding on rule 0; got {errs}"


def test_type_map_python_recursive_call_caught():
    """Python-only `(?P>name)` recursive calls are also rejected."""
    result = run_validator(
        FIXTURES / "invalid_type_map_python_recursive.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("Python-only" in e["message"] for e in errs), \
        f"expected Python-syntax finding for recursive call; got {errs}"


def test_type_map_unknown_match_value_caught():
    """`match` is a closed enum {exact, regex}; typos must be rejected, not silently skipped."""
    result = run_validator(
        FIXTURES / "invalid_type_map_unknown_match.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("'exact' | 'regex'" in e["message"] and "prefix" in e["message"] for e in errs), \
        f"expected unknown-match finding; got {errs}"


def test_type_map_legacy_wrapped_shape_warned():
    """The legacy wrapped `{native_to_arrow: {rules: [...]}}` shape is no
    longer the on-disk shape. Authors who haven't migrated must see a hint."""
    result = run_validator(
        FIXTURES / "invalid_type_map_legacy_wrapped.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    warns = warnings_of(result, "type-map-rule")
    assert any("pre-migration type-map shape" in w["message"] for w in warns), \
        f"expected legacy-shape warning; got {warns}"


def test_type_map_legacy_method_list_caught():
    """Top-level list with legacy `method` key (most common transcription of
    the old shape) must surface the rename pointer, not just opaque per-rule
    errors."""
    result = run_validator(
        FIXTURES / "invalid_type_map_legacy_method_list.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    warns = warnings_of(result, "type-map-rule")
    assert any("pre-migration type-map shape" in w["message"]
               and "method" in w["message"]
               for w in warns), \
        f"expected legacy-method-list warning; got {warns}"


def test_type_map_legacy_rules_keyed_caught():
    """`{rules: [...]}` object wrapper (variant 2 of the legacy shape) also
    surfaces the migration hint."""
    result = run_validator(
        FIXTURES / "invalid_type_map_legacy_rules_keyed.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    warns = warnings_of(result, "type-map-rule")
    assert any("pre-migration type-map shape" in w["message"] for w in warns), \
        f"expected legacy-rules-keyed warning; got {warns}"


def test_storage_kind_malformed_sibling_type_map_surfaced(tmp_path):
    """Storage-kind branch must NOT silently swallow OSError/JSONDecodeError.
    Mirror the api/db branch's error surfacing."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["kind"] = "file"
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text("{")  # malformed JSON
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("could not be read or parsed" in e["message"] for e in errs), \
        f"storage-kind malformed sibling JSON must be surfaced; got {errs}"


def test_storage_kind_legacy_wrapped_sibling_type_map_surfaced(tmp_path):
    """Storage-kind branch must reject non-list sibling type-map shape with
    the same 'must be a non-empty array' error as api/db. Mirrors the api/db
    branch's list-shape guard — without it the storage branch would silently
    no-op on a legacy-wrapped (`{native_to_arrow: {rules: [...]}}`) sibling."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["kind"] = "stdout"
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(json.dumps({
        "native_to_arrow": {"rules": [
            {"method": "exact", "native": "X", "canonical": "Utf8"}
        ]}
    }))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert any("non-empty array" in e["message"] for e in errs), \
        f"storage-kind non-list sibling must be flagged; got {errs}"


def test_type_map_non_dict_entry_warned(tmp_path):
    """Mixed-content list `[{valid}, "garbage"]`: dict entries are validated;
    non-dict entries surface a warning instead of silent drop."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text(json.dumps([
        {"match": "exact", "native": "BIGINT", "canonical": "Int64"},
        "stray-string",
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    warns = warnings_of(result, "type-map-rule")
    assert any("not an object" in w["message"] and w["path"] == "/1" for w in warns), \
        f"expected non-dict-entry warning; got {warns}"


def test_type_map_python_backreference_caught():
    """Python-only `(?P=name)` backreferences must also be rejected."""
    result = run_validator(
        FIXTURES / "invalid_type_map_python_backref.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("Python-only" in e["message"] for e in errs), \
        f"expected Python-syntax finding for backref; got {errs}"


def test_unhashable_rule_value_does_not_crash(tmp_path):
    """A `match`/`native` that isn't a primitive must not crash the validator,
    AND must surface a finding so the un-checkable rule isn't a silent skip.
    The non-string-native check supersedes the unhashable-key path for most
    cases (caught earlier with a clearer message)."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text(json.dumps([
        {"match": "exact", "native": ["X"], "canonical": "Utf8"},
        {"match": "exact", "native": "BIGINT", "canonical": "Int64"}
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    assert "findings" in result, f"expected structured output, got {result}"
    warns = warnings_of(result, "type-map-rule")
    assert any("native must be a string" in w["message"] for w in warns), \
        f"expected non-string-native warning so the rule isn't a silent skip; got {warns}"


def test_regex_rule_with_nonstring_canonical_still_compile_validated():
    """A broken regex must surface even when `canonical` is non-string —
    the canonical-string gate must not short-circuit regex compilation."""
    result = run_validator(
        FIXTURES / "invalid_type_map_regex_with_nonstring_canonical.json",
        "--semantic-only",
        schema_url=TYPE_MAP_READ_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] and e["path"] == "/0/native" for e in errs), \
        f"expected broken-regex finding on rule 0 (canonical=null); got {errs}"
    assert any("not a valid regex" in e["message"] and e["path"] == "/1/native" for e in errs), \
        f"expected broken-regex finding on rule 1 (canonical=list); got {errs}"


def test_empty_type_map_warns_under_semantic_only(tmp_path):
    """An empty type map must surface a warning under `--semantic-only`
    (Layer 1 owns the minItems error, but bypassing it would otherwise be a
    silent pass)."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text("[]")
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    warns = warnings_of(result, "type-map-rule")
    assert any("empty array" in w["message"] for w in warns), \
        f"expected empty-array warning; got {warns}"


def test_connector_validation_surfaces_sibling_rule_errors():
    """check_type_map_coverage must run rule checks on the sibling so a broken regex
    in type-map-read.json is caught when validating the connector, not only when
    invoked against the type map directly."""
    result = run_validator(
        FIXTURES / "connector_with_broken_type_map" / "connector.json",
        "--semantic-only",
    )
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] for e in errs), \
        f"expected broken sibling regex to surface via connector path; got {errs}"


# ---------------------------------------------------------------------------
# Write-direction maps (type-map-write.json) + uppercase pattern rule
# ---------------------------------------------------------------------------


WRITE_MAP_RULES = [
    {"match": "exact", "canonical": "Utf8", "native": "TEXT"},
    {
        "match": "regex",
        "canonical": "^Decimal(128|256)\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
        "native": "NUMERIC(${p}, ${s})",
    },
]


def test_write_map_rules_pass_under_write_filename(tmp_path):
    """Canonical-as-matcher / native-as-render rules (the write orientation)
    must validate cleanly when the file is named type-map-write.json."""
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps(WRITE_MAP_RULES))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    assert not errs, f"expected write-direction rules to validate under the write filename; got {errs}"


def test_direction_detected_by_filename(tmp_path):
    """Direction is a filename contract: the exact-rule `${}` gate applies to
    the RENDER side, which is `native` for write maps and `canonical` for
    read maps. The same two rules must flag opposite entries under the two
    filenames."""
    rules = [
        # ${} in native → render-side violation under WRITE only.
        {"match": "exact", "canonical": "Utf8", "native": "VARCHAR(${n})"},
        # ${} in canonical → render-side violation under READ only.
        {"match": "exact", "native": "TEXT", "canonical": "Utf8(${x})"},
    ]
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps(rules))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    paths = [e["path"] for e in errors_of(result, "type-map-rule")]
    assert paths == ["/0/native"], f"write direction must flag /0/native only; got {paths}"

    read_path = tmp_path / "type-map-read.json"
    read_path.write_text(json.dumps(rules))
    result = run_validator(read_path, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    paths = [e["path"] for e in errors_of(result, "type-map-rule")]
    assert paths == ["/1/canonical"], f"read direction must flag /1/canonical only; got {paths}"


def test_write_map_unbacked_placeholder_caught(tmp_path):
    """`${name}` in the write map's `native` must be backed by a `(?<name>…)`
    capture in `canonical` — the inverted form of the read-map rule."""
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps([
        {
            "match": "regex",
            "canonical": "^Decimal128\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
            "native": "NUMERIC(${p}, ${q})",
        }
    ]))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    assert any(
        e["path"] == "/0/native" and "${q}" in e["message"] and "canonical" in e["message"]
        for e in errs
    ), f"expected unbacked ${{q}} finding on /0/native; got {errs}"


def test_write_map_vocabulary_gap_warned(tmp_path):
    """A write map that misses canonical families gets a grouped rule-8
    warning (not an error — render_column_type overrides are legitimate)."""
    write_path = tmp_path / "type-map-write.json"
    write_path.write_text(json.dumps(WRITE_MAP_RULES))
    result = run_validator(write_path, "--semantic-only", schema_url=TYPE_MAP_WRITE_SCHEMA_URL)
    warns = warnings_of(result, "type-map-write-coverage")
    assert len(warns) == 1, f"expected one grouped vocabulary warning; got {warns}"
    msg = warns[0]["message"]
    listed = msg.split("families: ", 1)[1].split(". The write", 1)[0].split(", ")
    for family in ("Boolean", "Int64", "Json", "Timestamp (tz)"):
        assert family in listed, f"expected missing family {family!r} listed; got {listed}"
    assert "Utf8" not in listed, \
        f"Utf8 is covered and must not be listed as missing; got {listed}"
    # Note: ", ".split also bisects "Decimal128(p, s)" — check the fragment.
    assert "Decimal128(p" not in listed, \
        f"Decimal is covered by the regex rule and must not be listed; got {listed}"


def test_write_map_full_vocabulary_passes(tmp_path):
    """The postgres-reference-shaped write map fixture resolves every probe."""
    result = run_validator(
        FIXTURES / "valid_db_connector" / "type-map-write.json",
        "--semantic-only",
        schema_url=TYPE_MAP_WRITE_SCHEMA_URL,
    )
    errs = errors_of(result, "type-map-rule")
    assert not errs, f"expected reference write map to pass rule checks; got {errs}"
    warns = warnings_of(result, "type-map-write-coverage")
    assert not warns, f"expected full vocabulary coverage; got {warns}"


def test_write_map_vocabulary_gap_surfaces_from_connector_path(tmp_path):
    """The rule-8 probe must also run when the connector is validated with
    its siblings, not only against the standalone write map."""
    base = json.loads((FIXTURES / "valid_db_connector" / "connector.json").read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(
        (FIXTURES / "valid_db_connector" / "type-map-read.json").read_text()
    )
    (tmp_path / "type-map-write.json").write_text(json.dumps(WRITE_MAP_RULES))
    result = run_validator(doc_path, "--semantic-only")
    warns = warnings_of(result, "type-map-write-coverage")
    assert warns and "Boolean" in warns[0]["message"], \
        f"expected vocabulary-gap warning via connector path; got {warns}"


def test_read_regex_lowercase_pattern_warned(tmp_path):
    """Read-map regex patterns are matched against UPPERCASED natives;
    lowercase literals are dead rules and must warn. Capture group names
    and escapes (\\d) stay exempt."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text(json.dumps([
        {"match": "regex", "native": "^varchar\\((?<len>\\d+)\\)$", "canonical": "Utf8"},
        {"match": "regex", "native": "^NUMERIC\\((?<p>\\d+)\\)$", "canonical": "Decimal128(${p}, 0)"},
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    warns = warnings_of(result, "type-map-rule")
    lowercase_warns = [w for w in warns if "UPPERCASED" in w["message"]]
    assert len(lowercase_warns) == 1 and lowercase_warns[0]["path"] == "/0/native", \
        f"expected exactly one uppercase warning on /0/native; got {warns}"


def test_read_exact_lowercase_not_warned(tmp_path):
    """Exact rules are normalized automatically by the engine — lowercase
    exact natives must not trigger the uppercase warning."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text(json.dumps([
        {"match": "exact", "native": "jsonb", "canonical": "Json"},
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    warns = [w for w in warnings_of(result, "type-map-rule") if "UPPERCASED" in w["message"]]
    assert not warns, f"exact rules must be exempt from the uppercase warning; got {warns}"


def test_unrecognized_filename_direction_default_warned(tmp_path):
    """A type map validated under a filename that is neither
    type-map-read.json nor type-map-write.json silently got READ semantics
    before; now the defaulted direction must surface as a warning so a
    misplaced write map's vanished write-direction checks aren't silent."""
    odd_path = tmp_path / "some-map.json"
    odd_path.write_text(json.dumps(WRITE_MAP_RULES))
    result = run_validator(odd_path, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    warns = warnings_of(result, "type-map-rule")
    assert any("direction defaulted to 'read'" in w["message"] for w in warns), \
        f"expected direction-default warning for unrecognized filename; got {warns}"
    # Under the recognized filenames the warning must NOT fire.
    for name in ("type-map-read.json", "type-map-write.json"):
        good_path = tmp_path / name
        good_path.write_text(json.dumps(WRITE_MAP_RULES))
        result = run_validator(good_path, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
        warns = warnings_of(result, "type-map-rule")
        assert not any("direction defaulted" in w["message"] for w in warns), \
            f"direction-default warning must not fire for {name}; got {warns}"


def test_escaped_lowercase_letter_not_silent(tmp_path):
    """An unknown lowercase-letter escape (`\\q`) cannot slip past the
    uppercase check unseen: Python's `re` rejects unknown ASCII-letter
    escapes outright, so the rule surfaces as a compile ERROR before the
    warning stage. Escaped punctuation (`\\(`) and known class escapes
    (`\\d`, `\\s`) stay exempt from the uppercase warning."""
    tm = tmp_path / "type-map-read.json"
    tm.write_text(json.dumps([
        {"match": "regex", "native": "^NUMERIC\\(\\q\\)$", "canonical": "Utf8"},
        {"match": "regex", "native": "^VARCHAR\\(\\d+\\)\\s*$", "canonical": "Utf8"},
    ]))
    result = run_validator(tm, "--semantic-only", schema_url=TYPE_MAP_READ_SCHEMA_URL)
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] and e["path"] == "/0/native" for e in errs), \
        f"expected \\q rule to fail the compile gate; got {errs}"
    warns = [w for w in warnings_of(result, "type-map-rule") if "UPPERCASED" in w["message"]]
    assert not warns, \
        f"the all-uppercase rule with \\d/\\s escapes must not warn; got {warns}"


def test_tls_consistency_uppercase_verify_modes_caught(tmp_path):
    """MySQL-style VERIFY_CA / VERIFY_IDENTITY enum values must trigger the
    ssl_ca_certificate requirement (the check normalizes case and _/-)."""
    base = json.loads((FIXTURES / "valid_db_connector" / "connector.json").read_text())
    inputs = base["connection_contract"]["inputs"]
    inputs["ssl_mode"] = {
        "source": "user",
        "phase": "pre_auth",
        "storage": "connection.parameters",
        "type": "string",
        "required": False,
        "default": "PREFERRED",
        "enum": ["DISABLED", "PREFERRED", "REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"],
    }
    inputs.pop("ssl_ca_certificate", None)
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "tls-consistency")
    assert any("ssl_ca_certificate" in e["message"] for e in errs), \
        f"expected VERIFY_CA/VERIFY_IDENTITY to require ssl_ca_certificate; got {errs}"
    # Positive counterpart: declaring the CA input clears the finding.
    inputs["ssl_ca_certificate"] = {
        "source": "user",
        "phase": "pre_auth",
        "storage": "secrets",
        "type": "string",
        "required": False,
        "secret": True,
    }
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "tls-consistency")
    assert not errs, f"expected no tls-consistency error once ssl_ca_certificate declared; got {errs}"


def test_storage_kind_write_map_sibling_rule_checked(tmp_path):
    """The storage-kind branch must rule-check a present type-map-write.json
    with WRITE direction — a broken matcher regex (in `canonical` for the
    write direction) must surface."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    base["kind"] = "file"
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-write.json").write_text(json.dumps([
        {"match": "regex", "canonical": "^Decimal128([0-9", "native": "NUMERIC"}
    ]))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-rule")
    assert any("not a valid regex" in e["message"] and e["path"] == "/0/canonical" for e in errs), \
        f"storage-kind write-map sibling must be rule-checked in write direction; got {errs}"


def test_read_coverage_normalizes_native_case(tmp_path):
    """Endpoint natives are matched after UPPERCASE + whitespace-collapse
    normalization, so an uppercase exact rule covers a lowercase endpoint
    native (mirrors the engine)."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(json.dumps([
        {"match": "exact", "native": "STRING", "canonical": "Utf8"},
        {"match": "exact", "native": "BOOLEAN", "canonical": "Boolean"},
    ]))
    src = FIXTURES / "valid_api_connector"
    (tmp_path / "endpoints").mkdir()
    (tmp_path / "endpoints" / "ping.json").write_text((src / "endpoints" / "ping.json").read_text())
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert not errs, f"expected lowercase endpoint natives to resolve via uppercase rules; got {errs}"


def test_read_coverage_collapses_native_whitespace(tmp_path):
    """The other half of native normalization: runs of whitespace collapse
    to a single space, so 'double  precision' (two spaces) matches an
    exact rule authored 'DOUBLE PRECISION'."""
    base = json.loads(VALID_API_CONNECTOR.read_text())
    doc_path = tmp_path / "connector.json"
    doc_path.write_text(json.dumps(base))
    (tmp_path / "type-map-read.json").write_text(json.dumps([
        {"match": "exact", "native": "DOUBLE PRECISION", "canonical": "Float64"},
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
                            "amount": {
                                "type": "number",
                                "native_type": "double  precision",
                                "arrow_type": "Float64",
                            }
                        },
                    },
                },
            }
        },
    }))
    result = run_validator(doc_path, "--semantic-only")
    errs = errors_of(result, "type-map-coverage")
    assert not errs, \
        f"expected multi-space native to collapse and match single-space rule; got {errs}"


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
