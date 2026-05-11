"""Tests for scripts/validate_pipeline.py.

By default these tests run with `--semantic-only` so they don't depend on
network access to the live schema host. The `network`-marked tests fetch the
real schemas; CI can skip them with `-m "not network"`.

Run all: `pytest tests/pipeline_validator/`
Run offline only: `pytest tests/pipeline_validator/ -m "not network"`
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate_pipeline.py"
FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES_GLOB = list(REPO_ROOT.glob("skills/*-spec/examples/*.example.json"))

ENTITY_FOR_VALID = {
    "valid_pipeline.json": "pipeline",
    "valid_stream.json": "stream",
    "valid_connection.json": "connection",
    "valid_database_endpoint.json": "database_endpoint",
}


def run_validator(document_path: Path, entity: str, *extra: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--entity", entity,
            "--document", str(document_path),
            *extra,
        ],
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
@pytest.mark.parametrize(
    "filename,entity", sorted(ENTITY_FOR_VALID.items()), ids=lambda v: v if isinstance(v, str) else ""
)
def test_layer1_valid_fixtures_pass_against_live_schema(filename, entity):
    """Network test that exercises the schema fetch path per entity."""
    result = run_validator(FIXTURES / filename, entity)
    error_findings = [f for f in result["findings"] if f["severity"] == "error"]
    assert not error_findings, f"unexpected errors for {filename}: {error_findings}"
    assert result["passed"] is True


def test_schema_fetch_failure_is_diagnosed():
    bad_url = "http://127.0.0.1:1/nonexistent.json"
    result = run_validator(
        FIXTURES / "valid_pipeline.json",
        "pipeline",
        "--schema-url", bad_url,
        "--no-cache",
    )
    fetch_errors = [
        f for f in result["findings"]
        if f["validator"] == "json-schema" and "fetch" in f["message"].lower()
    ]
    assert fetch_errors, f"expected a schema-fetch finding; got {result['findings']}"
    assert result["passed"] is False


# ---------------------------------------------------------------------------
# Valid fixtures — semantic-only pass
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,entity", sorted(ENTITY_FOR_VALID.items()), ids=lambda v: v if isinstance(v, str) else ""
)
def test_valid_fixtures_pass_semantic(filename, entity):
    result = run_validator(FIXTURES / filename, entity, "--semantic-only")
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"{filename}: {errors}"
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Reference examples — integration
# ---------------------------------------------------------------------------


def _example_entity(path: Path) -> str | None:
    """Map a `skills/<entity>-spec/examples/*.example.json` to the validator entity."""
    parts = path.parts
    try:
        idx = parts.index("skills")
    except ValueError:
        return None
    if idx + 1 >= len(parts):
        return None
    spec_dir = parts[idx + 1]
    if spec_dir == "endpoint-spec":
        return "database_endpoint"
    if spec_dir == "pipeline-spec":
        return "pipeline"
    if spec_dir == "stream-spec":
        return "stream"
    if spec_dir == "connection-spec":
        return "connection"
    return None


@pytest.mark.parametrize("example", EXAMPLES_GLOB, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_reference_example_passes_semantic_validation(example):
    """Every shipped reference example must pass semantic validation."""
    entity = _example_entity(example)
    assert entity is not None, f"could not map {example} to a validator entity"
    result = run_validator(example, entity, "--semantic-only")
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"{example.relative_to(REPO_ROOT)}: {errors}"


def test_examples_glob_is_non_empty():
    """Guard against the parametrize collapsing to zero cases silently."""
    assert len(EXAMPLES_GLOB) >= 4, f"expected ≥ 4 reference examples, found {len(EXAMPLES_GLOB)}"


# ---------------------------------------------------------------------------
# Layer 2 — reserved-field
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entity,field,sentinel",
    [
        ("pipeline", "pipeline_id", "abc-123"),
        ("pipeline", "version", 1),
        ("pipeline", "org_id", "d7a11991-2795-49d1-a858-c7e58ee5ecc6"),
        ("pipeline", "created_at", "2026-05-09T00:00:00Z"),
        ("stream", "stream_id", "abc-123"),
        ("stream", "schema_hash", "sha256:deadbeef"),
        ("stream", "assignments_hash", "deadbeef"),
        ("stream", "source_to_generic", {"id": "string"}),
        ("connection", "connection_id", "abc-123"),
        ("connection", "connector_id", "abc-456"),
        ("connection", "connector_version", "1.0.0"),
        ("connection", "auth_state", {"type": "api_key"}),
        ("database_endpoint", "endpoint_id", "abc-789"),
        ("database_endpoint", "schema_hash", "sha256:cafebabe"),
    ],
)
def test_reserved_field_caught(tmp_path, entity, field, sentinel):
    valid_file = next(
        f for f, e in ENTITY_FOR_VALID.items() if e == entity
    )
    base = json.loads((FIXTURES / valid_file).read_text())
    base[field] = sentinel
    doc_path = tmp_path / f"reserved_{entity}_{field}.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, entity, "--semantic-only")
    errs = errors_of(result, "reserved-field")
    assert any(e["path"] == f"/{field}" for e in errs), (
        f"expected reserved-field finding at /{field}; got {result['findings']}"
    )


def test_reserved_assignments_hash_inside_mapping_caught(tmp_path):
    base = json.loads((FIXTURES / "valid_stream.json").read_text())
    base.setdefault("mapping", {})["assignments_hash"] = "deadbeef"
    doc_path = tmp_path / "stream_mapping_hash.json"
    doc_path.write_text(json.dumps(base))
    result = run_validator(doc_path, "stream", "--semantic-only")
    errs = errors_of(result, "reserved-field")
    assert any(e["path"] == "/mapping/assignments_hash" for e in errs), (
        f"expected reserved-field finding inside mapping; got {result['findings']}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — versioned-id-format
# ---------------------------------------------------------------------------


def test_pipeline_versioned_ids_caught():
    result = run_validator(
        FIXTURES / "invalid_pipeline_versioned_id.json", "pipeline", "--semantic-only"
    )
    errs = errors_of(result, "versioned-id-format")
    paths = sorted(e["path"] for e in errs)
    assert "/connections/source" in paths, f"expected source id error; got {paths}"
    assert "/connections/destinations/0" in paths, f"expected destinations[0] id error; got {paths}"


def test_stream_pipeline_id_must_not_be_versioned():
    result = run_validator(
        FIXTURES / "invalid_stream_pipeline_id_versioned.json", "stream", "--semantic-only"
    )
    errs = errors_of(result, "versioned-id-format")
    assert any(e["path"] == "/pipeline_id" for e in errs), (
        f"expected /pipeline_id versioned-id error; got {errs}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — schedule-shape
# ---------------------------------------------------------------------------


def test_schedule_manual_with_cron_or_interval_caught():
    result = run_validator(
        FIXTURES / "invalid_schedule_manual_with_cron.json", "pipeline", "--semantic-only"
    )
    errs = errors_of(result, "schedule-shape")
    paths = sorted(e["path"] for e in errs)
    assert "/schedule/cron_expression" in paths
    assert "/schedule/interval_minutes" in paths


def test_schedule_bad_timezone_caught():
    result = run_validator(
        FIXTURES / "invalid_schedule_bad_timezone.json", "pipeline", "--semantic-only"
    )
    errs = errors_of(result, "schedule-shape")
    assert any(e["path"] == "/schedule/timezone" for e in errs), (
        f"expected timezone finding; got {errs}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — runtime-ranges
# ---------------------------------------------------------------------------


def test_runtime_ranges_caught():
    result = run_validator(FIXTURES / "invalid_runtime_ranges.json", "pipeline", "--semantic-only")
    errs = errors_of(result, "runtime-ranges")
    paths = sorted(e["path"] for e in errs)
    assert "/runtime/error_handling/max_retries" in paths, f"expected max_retries finding; got {paths}"
    assert "/runtime/error_handling/retry_delay_seconds" in paths, (
        f"expected retry_delay_seconds finding (required when retries > 0); got {paths}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — endpoint-ref-shape
# ---------------------------------------------------------------------------


def test_endpoint_ref_bad_scope_and_dup_caught():
    result = run_validator(
        FIXTURES / "invalid_stream_endpoint_ref_scope.json", "stream", "--semantic-only"
    )
    errs = errors_of(result, "endpoint-ref-shape")
    paths = sorted(e["path"] for e in errs)
    assert any("/source/endpoint_ref/scope" in p for p in paths), (
        f"expected source scope finding; got {paths}"
    )
    assert any("/destinations/1/endpoint_ref" in p for p in paths), (
        f"expected destinations duplicate finding; got {paths}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — mapping-shape
# ---------------------------------------------------------------------------


def test_mapping_shape_violations_caught():
    result = run_validator(
        FIXTURES / "invalid_stream_mapping_both_value_keys.json", "stream", "--semantic-only"
    )
    errs = errors_of(result, "mapping-shape")
    messages = " | ".join(e["message"] for e in errs)
    assert "exactly one of 'expression' or 'constant'" in messages, messages
    assert "duplicate target.path" in messages, messages
    assert "expression.op='get'" in messages, messages


# ---------------------------------------------------------------------------
# Layer 2 — filter-operators
# ---------------------------------------------------------------------------


def test_filter_operators_caught():
    result = run_validator(
        FIXTURES / "invalid_stream_filter_operators.json", "stream", "--semantic-only"
    )
    errs = errors_of(result, "filter-operators")
    messages = " | ".join(f"{e['path']}: {e['message']}" for e in errs)
    assert "starts_with" in messages, f"expected non-DB operator finding; got {messages}"
    assert "is_null" in messages, f"expected unary-with-value finding; got {messages}"
    assert any(e["path"].endswith("/2/value") for e in errs), (
        f"expected missing-value finding for non-unary eq; got {messages}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — secret-ref-format
# ---------------------------------------------------------------------------


def test_secret_ref_format_caught():
    result = run_validator(
        FIXTURES / "invalid_connection_secret_ref.json", "connection", "--semantic-only"
    )
    errs = errors_of(result, "secret-ref-format")
    paths = sorted(e["path"] for e in errs)
    assert "/secret_refs/password" in paths
    assert "/secret_refs/ssl_ca_certificate" in paths


# ---------------------------------------------------------------------------
# Layer 2 — column-uniqueness
# ---------------------------------------------------------------------------


def test_column_uniqueness_caught():
    result = run_validator(
        FIXTURES / "invalid_endpoint_column_uniqueness.json",
        "database_endpoint",
        "--semantic-only",
    )
    errs = errors_of(result, "column-uniqueness")
    paths = sorted(e["path"] for e in errs)
    assert any("/columns/1/name" in p for p in paths), f"expected duplicate name finding; got {paths}"
    assert any("/columns/2/ordinal_position" in p for p in paths), (
        f"expected duplicate ordinal_position finding; got {paths}"
    )
    assert any("/primary_keys/0" in p for p in paths), (
        f"expected primary_keys references-no-column finding; got {paths}"
    )


# ---------------------------------------------------------------------------
# Layer 2 — pipeline-stream-consistency (bundle-root)
# ---------------------------------------------------------------------------


def test_pipeline_stream_consistency_inconsistent_caught():
    bundle = FIXTURES / "pipeline_consistency" / "inconsistent_dest_connection"
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    messages = " | ".join(e["message"] for e in errs)
    assert "destinations" in messages, f"expected destination-mismatch finding; got {errs}"


def test_pipeline_stream_consistency_consistent_passes():
    bundle = FIXTURES / "pipeline_consistency" / "consistent"
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    assert not errs, f"unexpected errors on consistent bundle: {errs}"


# ---------------------------------------------------------------------------
# Layer 2 — status-lifecycle
# ---------------------------------------------------------------------------


def test_status_active_with_empty_streams_caught():
    result = run_validator(
        FIXTURES / "invalid_pipeline_active_no_streams.json", "pipeline", "--semantic-only"
    )
    errs = errors_of(result, "status-lifecycle")
    assert any("at least one stream" in e["message"].lower() for e in errs), (
        f"expected empty-streams finding; got {errs}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_malformed_json_diagnosed(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text('{"alias":')
    result = run_validator(bad, "pipeline", "--semantic-only")
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert errs, f"expected a json-schema finding for malformed JSON; got {result['findings']}"
    assert result["passed"] is False


def test_missing_document_path_diagnosed(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    result = run_validator(missing, "pipeline", "--semantic-only")
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert errs, f"expected a json-schema finding for missing path; got {result['findings']}"
    assert result["passed"] is False


def test_semantic_and_json_only_are_mutually_exclusive():
    proc = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--entity", "pipeline",
            "--document", str(FIXTURES / "valid_pipeline.json"),
            "--semantic-only", "--json-only",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "mutually exclusive" in proc.stderr


def test_multiple_validators_all_fire(tmp_path):
    """A pipeline that violates schedule-shape AND has a reserved field should report both."""
    base = json.loads((FIXTURES / "invalid_schedule_manual_with_cron.json").read_text())
    base["pipeline_id"] = "abc-123"
    doc = tmp_path / "multi.json"
    doc.write_text(json.dumps(base))
    result = run_validator(doc, "pipeline", "--semantic-only")
    ids = {f["validator"] for f in result["findings"] if f["severity"] == "error"}
    assert {"reserved-field", "schedule-shape"}.issubset(ids), f"expected both validator ids; got {ids}"
