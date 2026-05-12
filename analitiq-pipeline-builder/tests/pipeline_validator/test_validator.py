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


@pytest.mark.network
@pytest.mark.parametrize(
    "filename,entity",
    [
        ("invalid_database_endpoint_bare_arrow_type.json", "database_endpoint"),
        ("invalid_stream_bare_arrow_type.json", "stream"),
    ],
)
def test_bare_parameterized_arrow_type_rejected(filename, entity):
    """The published schema regex rejects bare parameterized Arrow types.

    Pins the contract change in PR #34 — Timestamp, Decimal128, Time64, List, Struct
    et al. must carry parameters. A regression that re-introduces a bare form,
    or a schema-host change that loosens the regex, will be caught here.

    The database_endpoint case produces a path-specific error
    (/columns/<n>/arrow_type); the stream schema's mapping uses anyOf so the
    error bubbles up to /mapping. Each case asserts the strongest signal
    available for its entity.
    """
    result = run_validator(FIXTURES / filename, entity)
    schema_errors = [
        f for f in result["findings"]
        if f["validator"] == "json-schema" and f["severity"] == "error"
    ]
    assert schema_errors, f"expected Layer-1 error for {filename}; got {result['findings']}"
    assert result["passed"] is False

    if entity == "database_endpoint":
        arrow_type_path_errors = [f for f in schema_errors if f["path"].endswith("/arrow_type")]
        assert arrow_type_path_errors, (
            f"expected a Layer-1 error path ending in /arrow_type; got paths "
            f"{[f['path'] for f in schema_errors]}"
        )
    else:
        # Stream mapping errors bubble to /mapping; assert the offending bare
        # values surface in the error blob so a future "no longer rejects
        # bare arrow_type" regression breaks this test.
        blob = " ".join(f.get("message", "") + " " + f.get("path", "") for f in schema_errors)
        assert "Decimal128" in blob and "arrow_type" in blob, (
            f"expected stream error to surface the bare arrow_type value; got {schema_errors}"
        )


@pytest.mark.network
@pytest.mark.parametrize(
    "entity,patch",
    [
        ("database_endpoint", lambda doc: doc["columns"][0].pop("arrow_type")),
        ("stream", lambda doc: doc["mapping"]["assignments"][0]["target"].pop("arrow_type")),
    ],
    ids=["database_endpoint", "stream"],
)
def test_missing_arrow_type_rejected(tmp_path, entity, patch):
    """`arrow_type` is now required on every column and every mapping target."""
    source = "valid_database_endpoint.json" if entity == "database_endpoint" else "valid_stream.json"
    doc = json.loads((FIXTURES / source).read_text())
    patch(doc)
    target = tmp_path / f"missing_arrow_type_{entity}.json"
    target.write_text(json.dumps(doc))
    result = run_validator(target, entity)
    schema_errors = [
        f for f in result["findings"]
        if f["validator"] == "json-schema" and f["severity"] == "error"
    ]
    assert any("arrow_type" in f.get("message", "") or "arrow_type" in f.get("path", "")
               for f in schema_errors), (
        f"expected required-field error mentioning arrow_type; got {result['findings']}"
    )
    assert result["passed"] is False


@pytest.mark.network
@pytest.mark.parametrize(
    "arrow_type",
    [
        # Scalars with parameters
        "Timestamp(MICROSECOND, +05:30)",
        "Timestamp(MICROSECOND, Etc/GMT+5)",
        "Timestamp(NANOSECOND)",
        "Time32(SECOND)",
        "Time32(MILLISECOND)",
        "Time64(NANOSECOND)",
        "Duration(MICROSECOND)",
        "Interval(YEAR_MONTH)",
        "FixedSizeBinary(16)",
        "Decimal256(76, 0)",
        # "Large" variants of bare scalars
        "LargeUtf8",
        "LargeBinary",
        # Nested types
        "List<Int64>",
        "LargeList<Int64>",
        "FixedSizeList<Int64>[8]",
        "Map<Utf8, Int64>",
        "Dictionary<Int32, Utf8>",
        "Struct<id:Int64, name:Utf8>",
        "SparseUnion<Int64, Utf8>",
        "DenseUnion<Int64, Utf8>",
        "RunEndEncoded<Int32, Utf8>",
    ],
)
def test_layer1_accepts_fully_qualified_arrow_type_variants(tmp_path, arrow_type):
    """Each fully-qualified variant from the canonical examples block must pass Layer 1.

    Probes every branch of the published regex — scalar parameterized forms,
    Large* variants, all nested forms, and the union / run-end encoded
    extensions. If the schema host narrows the regex by mistake, one of these
    will start failing.
    """
    doc = json.loads((FIXTURES / "valid_database_endpoint.json").read_text())
    doc["columns"][0]["arrow_type"] = arrow_type
    target = tmp_path / "variant.json"
    target.write_text(json.dumps(doc))
    result = run_validator(target, "database_endpoint")
    errors = [f for f in result["findings"] if f["severity"] == "error"]
    assert not errors, f"unexpected errors for arrow_type={arrow_type!r}: {errors}"


@pytest.mark.network
@pytest.mark.parametrize(
    "arrow_type,why",
    [
        ("Decimal128(40, 0)", "precision 40 out of Decimal128 range (max 38)"),
        ("Decimal256(80, 0)", "precision 80 out of Decimal256 range (max 76)"),
        ("FixedSizeBinary(0)", "byte width must be >= 1"),
        ("FixedSizeList<Int64>", "missing trailing [N] length"),
        ("Map<Utf8>", "Map requires key and value type"),
        ("Timestamp()", "empty parens — unit is required"),
        ("Time32(MICROSECOND)", "Time32 only accepts SECOND or MILLISECOND"),
        ("Time64(SECOND)", "Time64 only accepts MICROSECOND or NANOSECOND"),
        ("Interval(MICROSECOND)", "Interval accepts IntervalUnit, not TimeUnit"),
        ("decimal128(12, 2)", "PascalCase required — lowercase rejected"),
    ],
)
def test_layer1_rejects_malformed_arrow_type(tmp_path, arrow_type, why):
    """Each malformed variant must trip the regex, proving the constraint is real.

    Catches regressions where the schema host accidentally loosens a regex
    branch (e.g. allowing Time32(MICROSECOND) or decimal128 lowercase). The
    `why` column is documentation for future readers; the assertion only
    checks that validation fails.
    """
    doc = json.loads((FIXTURES / "valid_database_endpoint.json").read_text())
    doc["columns"][0]["arrow_type"] = arrow_type
    target = tmp_path / "malformed.json"
    target.write_text(json.dumps(doc))
    result = run_validator(target, "database_endpoint")
    arrow_type_errors = [
        f for f in result["findings"]
        if f["validator"] == "json-schema"
        and f["severity"] == "error"
        and f["path"].endswith("/arrow_type")
    ]
    assert arrow_type_errors, (
        f"expected schema error for arrow_type={arrow_type!r} ({why}); got {result['findings']}"
    )
    assert result["passed"] is False


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


@pytest.mark.network
@pytest.mark.parametrize("example", EXAMPLES_GLOB, ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_reference_example_passes_layer1(example):
    """Every reference example must also pass Layer 1 against the live schema.

    Without this the semantic sweep silently bypasses the regex constraint on
    `arrow_type` and friends, leaving the canonical examples (e.g. nested
    `Struct<…>`, fully-qualified `Timestamp(MICROSECOND, UTC)`) unverified
    against the contract they're meant to demonstrate.
    """
    entity = _example_entity(example)
    assert entity is not None, f"could not map {example} to a validator entity"
    result = run_validator(example, entity)
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


def _pipeline_with(tmp_path, schedule):
    base = json.loads((FIXTURES / "valid_pipeline.json").read_text())
    base["schedule"] = schedule
    p = tmp_path / "p.json"
    p.write_text(json.dumps(base))
    return p


@pytest.mark.parametrize(
    "schedule,expect_paths",
    [
        ({"type": "interval"}, ["/schedule/interval_minutes"]),
        ({"type": "interval", "interval_minutes": 30, "cron_expression": "cron(* * * * ? *)"},
         ["/schedule/cron_expression"]),
        ({"type": "cron"}, ["/schedule/cron_expression"]),
        ({"type": "cron", "cron_expression": "not-a-cron-spec"}, ["/schedule/cron_expression"]),
        ({"type": "cron", "cron_expression": "cron(0 2 * * ? *)", "interval_minutes": 30},
         ["/schedule/interval_minutes"]),
    ],
    ids=["interval-missing-minutes", "interval-with-cron", "cron-missing-expr",
         "cron-bad-pattern", "cron-with-interval"],
)
def test_schedule_branches_caught(tmp_path, schedule, expect_paths):
    result = run_validator(_pipeline_with(tmp_path, schedule), "pipeline", "--semantic-only")
    errs = errors_of(result, "schedule-shape")
    err_paths = sorted(e["path"] for e in errs)
    for expected in expect_paths:
        assert expected in err_paths, f"expected {expected} in {err_paths}"


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


def _pipeline_with_runtime(tmp_path, engine=None, runtime=None):
    base = json.loads((FIXTURES / "valid_pipeline.json").read_text())
    if engine is not None:
        base["engine"] = engine
    if runtime is not None:
        base["runtime"] = runtime
    p = tmp_path / "p.json"
    p.write_text(json.dumps(base))
    return p


@pytest.mark.parametrize(
    "engine,runtime,expected_path",
    [
        ({"vcpu": 0.1, "memory": 8192}, None, "/engine/vcpu"),
        ({"vcpu": 1, "memory": 512}, None, "/engine/memory"),
        (None, {"buffer_size": 50}, "/runtime/buffer_size"),
        (None, {"batching": {"batch_size": 0, "max_concurrent_batches": 3}},
         "/runtime/batching/batch_size"),
        (None, {"batching": {"batch_size": 200000, "max_concurrent_batches": 3}},
         "/runtime/batching/batch_size"),
        (None, {"batching": {"batch_size": 100, "max_concurrent_batches": 0}},
         "/runtime/batching/max_concurrent_batches"),
        (None, {"batching": {"batch_size": 100, "max_concurrent_batches": 200}},
         "/runtime/batching/max_concurrent_batches"),
        (None, {"error_handling": {"strategy": "dlq", "max_retries": 0,
                                   "retry_delay_seconds": 5}},
         "/runtime/error_handling/retry_delay_seconds"),
    ],
    ids=["vcpu-below-floor", "memory-below-floor", "buffer-below-floor",
         "batch-size-below-min", "batch-size-above-max",
         "concurrent-batches-below-min", "concurrent-batches-above-max",
         "retries-zero-with-delay"],
)
def test_runtime_range_branches_caught(tmp_path, engine, runtime, expected_path):
    p = _pipeline_with_runtime(tmp_path, engine=engine, runtime=runtime)
    result = run_validator(p, "pipeline", "--semantic-only")
    errs = errors_of(result, "runtime-ranges")
    paths = [e["path"] for e in errs]
    assert expected_path in paths, f"expected {expected_path} finding; got {paths}"


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


def test_pipeline_stream_consistency_inconsistent_dest_caught():
    bundle = FIXTURES / "pipeline_consistency" / "inconsistent_dest_connection"
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    messages = " | ".join(e["message"] for e in errs)
    assert "destinations" in messages, f"expected destination-mismatch finding; got {errs}"


def test_pipeline_stream_consistency_inconsistent_source_caught():
    bundle = FIXTURES / "pipeline_consistency" / "inconsistent_source"
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    paths = [e["path"] for e in errs]
    assert "/connections/source" in paths, f"expected source-mismatch finding; got {errs}"


def test_pipeline_stream_consistency_consistent_passes():
    bundle = FIXTURES / "pipeline_consistency" / "consistent"
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    findings = [f for f in result["findings"]
                if f["validator"] == "pipeline-stream-consistency"]
    # Locks in zero findings (no errors AND no stealth warnings) when the
    # bundle truly is consistent — the warning previously masked by an
    # error-only assertion.
    assert not findings, f"unexpected pipeline-stream-consistency findings: {findings}"


def test_pipeline_stream_consistency_warning_without_bundle():
    """Without --bundle-root, the validator emits a warning rather than silently no-op'ing."""
    result = run_validator(FIXTURES / "valid_pipeline.json", "pipeline", "--semantic-only")
    warns = warnings_of(result, "pipeline-stream-consistency")
    assert warns, f"expected a warning when --bundle-root is omitted; got {result['findings']}"


def test_pipeline_stream_consistency_ignores_sibling_pipelines(tmp_path):
    """A bundle containing a second pipeline must not pollute the current pipeline's check.

    Regression for the bug where `rglob('streams/*.json')` picked up streams
    from every pipeline in the bundle and false-flagged them.
    """
    # Build a bundle with two pipelines under it; only the wise_to_postgresql
    # one is consistent. The other has a stream pointing at unknown connections.
    consistent_src = FIXTURES / "pipeline_consistency" / "consistent"
    import shutil
    bundle = tmp_path / "bundle"
    shutil.copytree(consistent_src, bundle)
    # Add a stray pipeline whose stream references unrelated connections.
    other_dir = bundle / "pipelines" / "other_pipeline"
    (other_dir / "streams").mkdir(parents=True)
    (other_dir / "pipeline.json").write_text(json.dumps({
        "$schema": "https://schemas.analitiq.ai/pipeline/latest.json",
        "alias": "other_pipeline",
        "connections": {
            "source": "other_source",
            "destinations": ["other_dest"],
        },
        "streams": [],
        "schedule": {"type": "manual"},
    }))
    (other_dir / "streams" / "stray.json").write_text(json.dumps({
        "$schema": "https://schemas.analitiq.ai/stream/latest.json",
        "alias": "stray",
        "pipeline_id": "other_pipeline",
        "source": {
            "endpoint_ref": {"scope": "connector",
                             "connection_id": "other_source",
                             "alias": "x"},
            "replication": {"method": "full_refresh"},
        },
        "destinations": [{
            "endpoint_ref": {"scope": "connection",
                             "connection_id": "other_dest",
                             "alias": "y"},
            "write": {"mode": "insert"},
        }],
    }))
    doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    findings = [f for f in result["findings"]
                if f["validator"] == "pipeline-stream-consistency"]
    assert not findings, (
        "sibling pipeline's streams must not affect this pipeline's consistency check; "
        f"got {findings}"
    )


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


def test_status_active_warns_without_bundle(tmp_path):
    """status=active with populated streams[] but no --bundle-root → warning."""
    base = json.loads((FIXTURES / "valid_pipeline.json").read_text())
    base["status"] = "active"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(base))
    result = run_validator(p, "pipeline", "--semantic-only")
    warns = warnings_of(result, "status-lifecycle")
    assert warns, f"expected status-lifecycle warning; got {result['findings']}"


def test_status_active_errors_when_no_stream_is_active(tmp_path):
    """status=active with bundle-root, but no stream file has status=active → error."""
    import shutil
    bundle_src = FIXTURES / "pipeline_consistency" / "consistent"
    bundle = tmp_path / "bundle"
    shutil.copytree(bundle_src, bundle)
    pipeline_doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    pdoc = json.loads(pipeline_doc.read_text())
    pdoc["status"] = "active"
    pipeline_doc.write_text(json.dumps(pdoc))
    # Stream's status is "draft" in the consistent fixture, so we should error.
    result = run_validator(pipeline_doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "status-lifecycle")
    assert any("no referenced stream file has status='active'" in e["message"] for e in errs), (
        f"expected no-active-stream finding; got {errs}"
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


def test_non_dict_document_diagnosed():
    """A valid JSON list / null / scalar must surface a clean Diagnostic, not a Python traceback."""
    result = run_validator(FIXTURES / "invalid_document_not_dict.json", "pipeline", "--semantic-only")
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert errs, f"expected a json-schema finding for non-dict root; got {result['findings']}"
    assert any("must be a JSON object" in e["message"] for e in errs), (
        f"expected 'must be a JSON object' diagnostic; got {errs}"
    )
    assert result["passed"] is False


def test_nonexistent_bundle_root_diagnosed(tmp_path):
    """Bad --bundle-root must produce a clean diagnostic, not silently underrun consistency."""
    missing = tmp_path / "does-not-exist"
    result = run_validator(
        FIXTURES / "valid_pipeline.json", "pipeline", "--semantic-only",
        "--bundle-root", str(missing),
    )
    errs = [f for f in result["findings"] if f["validator"] == "json-schema"]
    assert any("not an existing directory" in e["message"] for e in errs), (
        f"expected bundle-root diagnostic; got {errs}"
    )


def test_malformed_stream_file_in_bundle_caught(tmp_path):
    """A broken stream file in the bundle must emit a finding, not be silently skipped."""
    import shutil
    bundle_src = FIXTURES / "pipeline_consistency" / "consistent"
    bundle = tmp_path / "bundle"
    shutil.copytree(bundle_src, bundle)
    (bundle / "pipelines" / "wise_to_postgresql" / "streams" / "broken.json").write_text("{not json")
    pipeline_doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(pipeline_doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    assert any("broken.json" in e["message"] and "JSON" in e["message"] for e in errs), (
        f"expected JSON-parse finding for broken.json; got {errs}"
    )


def test_non_utf8_stream_file_in_bundle_caught(tmp_path):
    """A non-UTF-8 stream file must emit a finding, not crash the validator."""
    import shutil
    bundle_src = FIXTURES / "pipeline_consistency" / "consistent"
    bundle = tmp_path / "bundle"
    shutil.copytree(bundle_src, bundle)
    # Write raw bytes that aren't valid UTF-8.
    binary = bundle / "pipelines" / "wise_to_postgresql" / "streams" / "binary.json"
    binary.write_bytes(b"\xff\xfe\x00\x01not valid utf-8")
    pipeline_doc = bundle / "pipelines" / "wise_to_postgresql" / "pipeline.json"
    result = run_validator(pipeline_doc, "pipeline", "--semantic-only", "--bundle-root", str(bundle))
    errs = errors_of(result, "pipeline-stream-consistency")
    assert any("binary.json" in e["message"] and "UTF-8" in e["message"] for e in errs), (
        f"expected UTF-8 decode finding for binary.json; got {errs}"
    )


def test_strip_required_server_fields_walks_nested_required():
    """Unit-test for the Layer 1 pre-processor (load it via importlib to avoid CLI overhead)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("validate_pipeline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Use pipeline-reserved fields (pipeline_id, version, org_id) at every
    # level so the strip is expected to remove them; keep `alias` and
    # `user_field` as authored fields that must survive.
    schema = {
        "required": ["pipeline_id", "alias", "version"],
        "properties": {
            "mapping": {
                "type": "object",
                "required": ["assignments", "pipeline_id"],
                "properties": {"assignments": {"type": "array"}},
            },
        },
        "$defs": {
            "Inner": {"required": ["org_id", "user_field"]},
        },
        "allOf": [
            {"required": ["created_at", "alias"]},
        ],
    }
    out = mod._strip_required_server_fields(schema, "pipeline")
    assert out["required"] == ["alias"], f"top-level required not stripped: {out['required']}"
    assert out["properties"]["mapping"]["required"] == ["assignments"], (
        f"nested required not stripped: {out['properties']['mapping']['required']}"
    )
    assert out["$defs"]["Inner"]["required"] == ["user_field"], (
        f"$defs required not stripped: {out['$defs']['Inner']['required']}"
    )
    assert out["allOf"][0]["required"] == ["alias"], (
        f"allOf branch required not stripped: {out['allOf'][0]['required']}"
    )
    # Input schema was deep-cloned, not mutated.
    assert schema["required"] == ["pipeline_id", "alias", "version"], "input schema was mutated"
    assert schema["properties"]["mapping"]["required"] == ["assignments", "pipeline_id"], (
        "nested input was mutated"
    )


def test_schema_fetch_failure_does_not_suppress_semantic_findings(tmp_path):
    """Layer 1 fetch failure records a finding but Layer 2 still runs."""
    # Build a doc that violates a Layer 2 rule (reserved-field).
    base = json.loads((FIXTURES / "valid_pipeline.json").read_text())
    base["pipeline_id"] = "should-not-be-here"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(base))
    # Bad fetch URL — Layer 1 will fail, Layer 2 should still report reserved-field.
    bad_url = "http://127.0.0.1:1/nonexistent.json"
    result = run_validator(p, "pipeline", "--schema-url", bad_url, "--no-cache")
    fetch_errs = [f for f in result["findings"]
                  if f["validator"] == "json-schema" and "fetch" in f["message"].lower()]
    assert fetch_errs, f"expected schema-fetch finding; got {result['findings']}"
    reserved_errs = errors_of(result, "reserved-field")
    assert reserved_errs, (
        "Layer 2 must still run when Layer 1 fetch fails; "
        f"reserved-field finding missing in {result['findings']}"
    )


def test_multiple_validators_all_fire(tmp_path):
    """A pipeline that violates schedule-shape AND has a reserved field should report both."""
    base = json.loads((FIXTURES / "invalid_schedule_manual_with_cron.json").read_text())
    base["pipeline_id"] = "abc-123"
    doc = tmp_path / "multi.json"
    doc.write_text(json.dumps(base))
    result = run_validator(doc, "pipeline", "--semantic-only")
    ids = {f["validator"] for f in result["findings"] if f["severity"] == "error"}
    assert {"reserved-field", "schedule-shape"}.issubset(ids), f"expected both validator ids; got {ids}"
