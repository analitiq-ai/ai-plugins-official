#!/usr/bin/env python3
"""Validate an Analitiq pipeline, stream, connection, or database-endpoint document.

Layer 1: JSON Schema validation against the published schema URL (Draft 2020-12).
Layer 2: Semantic validators encoding rules that JSON Schema can't express.

Output: a single Diagnostics JSON object on stdout. Exit 0 iff `passed` is true.

Schemas are fetched from the published host (schemas.analitiq.ai), and
authored documents declare the same host in their `$schema` field — the
`$schema` const inside each schema locks that.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:
    print(
        json.dumps(
            {
                "passed": False,
                "findings": [
                    {
                        "validator": "json-schema",
                        "severity": "error",
                        "path": "",
                        "message": f"Missing dependency: {exc}. Install with `pip install jsonschema`.",
                    }
                ],
            }
        )
    )
    sys.exit(1)

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # Python < 3.9 — not supported by the plugin
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment,misc]

# Detect "tzdata missing" on Python ≥ 3.9 — `ZoneInfo` imports fine but every
# lookup raises because the system has no tzdata. We probe once at startup so
# `check_schedule_shape` can skip the IANA-name check entirely instead of
# false-flagging every legitimate timezone. The stderr warning below tells the
# user the check was skipped; we do not fall back to a regex-style "looks like
# a timezone" check, because tzdata-less environments are rare in practice and
# a partial check would be more confusing than no check at all.
_TZDATA_AVAILABLE = False
if ZoneInfo is not None:
    try:
        ZoneInfo("UTC")
        _TZDATA_AVAILABLE = True
    except Exception:  # noqa: BLE001 — any failure means tzdata is broken/missing
        print(
            "warning: zoneinfo is available but tzdata is missing — schedule.timezone "
            "validation will be skipped. Install the `tzdata` package to enable it.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Schema fetch + cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "analitiq" / "schemas"

ENTITY_SCHEMAS = {
    "pipeline": "https://schemas.analitiq.ai/pipeline/latest.json",
    "stream": "https://schemas.analitiq.ai/stream/latest.json",
    "connection": "https://schemas.analitiq.ai/connection/latest.json",
    "database_endpoint": "https://schemas.analitiq.ai/database-endpoint/latest.json",
}


def fetch_schema(url: str, cache: bool = True) -> dict:
    """Fetch a JSON schema from URL with atomic disk cache.

    Parses the JSON response *before* writing to disk so a malformed
    response can never poison the cache. Writes via a temp file +
    `os.replace` so a Ctrl-C mid-write leaves no truncated cache file.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text())
    with urllib.request.urlopen(url, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"schema fetch returned HTTP {resp.status} for {url}")
        body = resp.read().decode()
    schema = json.loads(body)
    tmp_path = cache_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(body)
        os.replace(tmp_path, cache_path)
    except OSError as exc:
        # Cache write failed (disk full, antivirus lock, etc.). The schema is
        # in memory and the caller can proceed; just clean up the temp file.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"warning: schema cache write failed: {exc}", file=sys.stderr)
    return schema


# ---------------------------------------------------------------------------
# Diagnostics helpers
# ---------------------------------------------------------------------------

VALIDATOR_IDS = {
    "json-schema",
    "reserved-field",
    "schedule-shape",
    "runtime-ranges",
    "endpoint-ref-shape",
    "mapping-shape",
    "filter-operators",
    "secret-ref-format",
    "column-uniqueness",
    "pipeline-stream-consistency",
    "status-lifecycle",
}


def finding(
    validator: str,
    severity: str,
    path: str,
    message: str,
    rule_doc: str | None = None,
) -> dict:
    assert validator in VALIDATOR_IDS, f"unknown validator id: {validator}"
    assert severity in ("error", "warning"), f"unknown severity: {severity}"
    out = {
        "validator": validator,
        "severity": severity,
        "path": path,
        "message": message,
    }
    if rule_doc:
        out["rule_doc"] = rule_doc
    return out


# ---------------------------------------------------------------------------
# Layer 1 — JSON Schema validation
# ---------------------------------------------------------------------------


def _strip_required_server_fields(schema: dict, entity: str) -> dict:
    """Return a deep-cloned schema with server-managed fields removed from every `required` array.

    The published pipeline/stream/connection schemas describe the canonical
    server-stamped document, so they mark fields like `pipeline_id`, `version`,
    `org_id`, `created_at`, `updated_at` as required at the JSON Schema level.
    Authored documents intentionally omit those fields (the registry stamps
    them on insert). This helper walks the schema (including nested objects,
    `$defs`, and `allOf`/`oneOf`/`anyOf` branches) and drops every reserved-
    field entry from each `required` array it encounters so authored documents
    can pass Layer 1. The `reserved-field` Layer 2 validator still catches the
    inverse case (an authored doc that *does* contain a server-managed field).

    The clone is deep so this helper never mutates its input. `fetch_schema`
    re-parses from disk on every call, so there's no in-memory cache to
    poison today — but a shallow clone would still leak edits into the input
    object the caller holds (e.g., the schema dict parsed once at the top of
    `main()` and reused for multiple validation passes in a long-running
    embedder). Deep-clone is the cheapest way to make the helper safe to
    compose.
    """
    server_fields = RESERVED_FIELDS_BY_ENTITY.get(entity, set())
    if not server_fields:
        return schema

    def _walk(node: Any) -> Any:
        if isinstance(node, dict):
            cloned: dict = {}
            for k, v in node.items():
                if k == "required" and isinstance(v, list):
                    cloned[k] = [r for r in v if r not in server_fields]
                else:
                    cloned[k] = _walk(v)
            return cloned
        if isinstance(node, list):
            return [_walk(x) for x in node]
        return node

    return _walk(schema)


def layer1_jsonschema(document: dict, schema: dict, entity: str) -> list[dict]:
    """Run Draft 2020-12 validation, mapping each error to a finding."""
    effective_schema = _strip_required_server_fields(schema, entity)
    validator = Draft202012Validator(effective_schema)
    findings: list[dict] = []
    for err in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path)):
        path = "/" + "/".join(str(p) for p in err.absolute_path)
        findings.append(
            finding(
                "json-schema",
                "error",
                path,
                err.message,
                rule_doc="https://schemas.analitiq.ai/",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Layer 2 — Semantic validators
# ---------------------------------------------------------------------------

RESERVED_FIELDS_BY_ENTITY: dict[str, set[str]] = {
    "pipeline": {
        "pipeline_id",
        "version",
        "org_id",
        "created_at",
        "updated_at",
    },
    "stream": {
        "stream_id",
        "version",
        "org_id",
        "created_at",
        "updated_at",
        "schema_hash",
        "assignments_hash",
        "source_schema_fingerprint",
        "target_schema_fingerprint",
        "source_schema_id",
        "target_schema_id",
        "source_to_generic",
        "generic_to_destination",
        "type_mapping_assignments_hash",
    },
    "connection": {
        "connection_id",
        "version",
        "org_id",
        "connector_id",
        "connector_version",
        "auth_state",
        "created_at",
        "updated_at",
    },
    "database_endpoint": {
        "endpoint_id",
        "connector_id",
        "connector_version",
        "connection_id",
        "schema_hash",
    },
}


CRON_RE = re.compile(r"^cron\(.+\)$")


DB_FILTER_OPERATORS = {
    "eq", "neq", "gt", "gte", "lt", "lte",
    "in", "not_in",
    "is_null", "is_not_null",
    "like", "ilike",
}
API_FILTER_OPERATORS = {
    "eq", "neq", "gt", "gte", "lt", "lte",
    "in", "not_in",
    "contains", "starts_with", "ends_with",
}
UNARY_OPERATORS = {"is_null", "is_not_null"}


SECRET_REF_PATTERNS = [
    re.compile(r"^secrets/.+"),
    re.compile(r"^connections/.+"),
    re.compile(r"^ssm:/.+"),
    re.compile(r"^arn:aws:secretsmanager:[^:]+:[^:]+:secret:.+"),
    re.compile(r"^arn:aws:ssm:[^:]+:[^:]+:parameter/.+"),
    re.compile(r"^s3://[^/]+/.+"),
]


# Per-entity rule_doc path for reserved-field findings. Auto-generating these
# from the entity name produces wrong paths for `database_endpoint` (the
# directory is `endpoints/`, not `database_endpoints/`; the filename uses a
# hyphen, not an underscore), so they're enumerated here.
_RESERVED_FIELD_RULE_DOC = {
    "pipeline": "pipelines/pipeline-schema-parameterization.md#server-managed-and-reserved-fields",
    "stream": "streams/stream-schema-parameterization.md#server-managed-and-reserved-fields",
    "connection": "connections/connection-schema-parameterization.md#server-managed-and-reserved-fields",
    "database_endpoint": "endpoints/database-endpoint-schema-parameterization.md#server-managed-and-reserved-fields",
}


# ---------------------------------------------------------------------------
# reserved-field
# ---------------------------------------------------------------------------


def check_reserved_fields(doc: dict, entity: str) -> list[dict]:
    reserved = RESERVED_FIELDS_BY_ENTITY.get(entity, set())
    findings: list[dict] = []
    rule_doc = _RESERVED_FIELD_RULE_DOC.get(entity, "")
    for field in sorted(reserved):
        if field in doc:
            findings.append(
                finding(
                    "reserved-field",
                    "error",
                    f"/{field}",
                    f"Reserved server-managed field '{field}' must not appear in authored {entity} documents.",
                    rule_doc=rule_doc,
                )
            )
    if entity == "stream":
        mapping = doc.get("mapping")
        if isinstance(mapping, dict) and "assignments_hash" in mapping:
            findings.append(
                finding(
                    "reserved-field",
                    "error",
                    "/mapping/assignments_hash",
                    "Reserved server-managed field 'assignments_hash' must not appear inside authored mapping.",
                    rule_doc=rule_doc,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# schedule-shape
# ---------------------------------------------------------------------------


def check_schedule_shape(doc: dict) -> list[dict]:
    findings: list[dict] = []
    schedule = doc.get("schedule")
    if not isinstance(schedule, dict):
        return findings
    stype = schedule.get("type", "manual")
    has_interval = "interval_minutes" in schedule
    has_cron = "cron_expression" in schedule
    if stype == "manual":
        if has_interval:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/interval_minutes",
                    "schedule.type=manual must not declare 'interval_minutes'.",
                    rule_doc="shared/scheduling.md",
                )
            )
        if has_cron:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/cron_expression",
                    "schedule.type=manual must not declare 'cron_expression'.",
                    rule_doc="shared/scheduling.md",
                )
            )
    elif stype == "interval":
        if not has_interval:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/interval_minutes",
                    "schedule.type=interval requires 'interval_minutes'.",
                    rule_doc="shared/scheduling.md",
                )
            )
        if has_cron:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/cron_expression",
                    "schedule.type=interval must not declare 'cron_expression'.",
                    rule_doc="shared/scheduling.md",
                )
            )
    elif stype == "cron":
        if not has_cron:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/cron_expression",
                    "schedule.type=cron requires 'cron_expression'.",
                    rule_doc="shared/scheduling.md",
                )
            )
        elif isinstance(schedule.get("cron_expression"), str) and not CRON_RE.match(
            schedule["cron_expression"]
        ):
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/cron_expression",
                    f"cron_expression {schedule['cron_expression']!r} must match 'cron(<spec>)'.",
                    rule_doc="shared/scheduling.md",
                )
            )
        if has_interval:
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/interval_minutes",
                    "schedule.type=cron must not declare 'interval_minutes'.",
                    rule_doc="shared/scheduling.md",
                )
            )
    tz = schedule.get("timezone")
    if isinstance(tz, str) and _TZDATA_AVAILABLE:
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            findings.append(
                finding(
                    "schedule-shape",
                    "error",
                    "/schedule/timezone",
                    f"timezone {tz!r} is not a valid IANA name.",
                    rule_doc="shared/scheduling.md",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# runtime-ranges
# ---------------------------------------------------------------------------


def _range_finding(path: str, message: str) -> dict:
    return finding(
        "runtime-ranges",
        "error",
        path,
        message,
        rule_doc="pipelines/pipeline-schema-parameterization.md#engine-and-runtime",
    )


def check_runtime_ranges(doc: dict) -> list[dict]:
    findings: list[dict] = []
    engine = doc.get("engine")
    if isinstance(engine, dict):
        vcpu = engine.get("vcpu")
        if isinstance(vcpu, (int, float)) and vcpu < 0.5:
            findings.append(_range_finding("/engine/vcpu", f"engine.vcpu must be >= 0.5; got {vcpu}."))
        memory = engine.get("memory")
        if isinstance(memory, int) and memory < 1024:
            findings.append(_range_finding("/engine/memory", f"engine.memory must be >= 1024; got {memory}."))
    runtime = doc.get("runtime")
    if not isinstance(runtime, dict):
        return findings
    bs = runtime.get("buffer_size")
    if isinstance(bs, int) and bs < 100:
        findings.append(_range_finding("/runtime/buffer_size", f"runtime.buffer_size must be >= 100; got {bs}."))
    batching = runtime.get("batching")
    if isinstance(batching, dict):
        batch_size = batching.get("batch_size")
        if isinstance(batch_size, int) and not (1 <= batch_size <= 100000):
            findings.append(
                _range_finding(
                    "/runtime/batching/batch_size",
                    f"runtime.batching.batch_size must be in [1, 100000]; got {batch_size}.",
                )
            )
        mcb = batching.get("max_concurrent_batches")
        if isinstance(mcb, int) and not (1 <= mcb <= 100):
            findings.append(
                _range_finding(
                    "/runtime/batching/max_concurrent_batches",
                    f"runtime.batching.max_concurrent_batches must be in [1, 100]; got {mcb}.",
                )
            )
    eh = runtime.get("error_handling")
    if isinstance(eh, dict):
        retries = eh.get("max_retries")
        delay = eh.get("retry_delay_seconds")
        if isinstance(retries, int) and not (0 <= retries <= 5):
            findings.append(
                _range_finding(
                    "/runtime/error_handling/max_retries",
                    f"runtime.error_handling.max_retries must be in [0, 5]; got {retries}.",
                )
            )
        if isinstance(retries, int):
            if retries > 0 and (delay is None or (isinstance(delay, int) and delay < 1)):
                findings.append(
                    _range_finding(
                        "/runtime/error_handling/retry_delay_seconds",
                        "retry_delay_seconds must be a positive integer when max_retries > 0.",
                    )
                )
            if retries == 0 and isinstance(delay, int) and delay != 0:
                findings.append(
                    _range_finding(
                        "/runtime/error_handling/retry_delay_seconds",
                        "retry_delay_seconds must be omitted or zero when max_retries == 0.",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# endpoint-ref-shape
# ---------------------------------------------------------------------------


def check_endpoint_ref_shape(doc: dict) -> list[dict]:
    findings: list[dict] = []

    def _check_ref(ref: Any, path: str) -> None:
        if not isinstance(ref, dict):
            return
        scope = ref.get("scope")
        if scope not in {"connector", "connection"}:
            findings.append(
                finding(
                    "endpoint-ref-shape",
                    "error",
                    f"{path}/scope",
                    f"endpoint_ref.scope must be 'connector' or 'connection'; got {scope!r}.",
                    rule_doc="streams/stream-schema-parameterization.md#endpoint-refs",
                )
            )

    source = doc.get("source")
    if isinstance(source, dict):
        _check_ref(source.get("endpoint_ref"), "/source/endpoint_ref")
    destinations = doc.get("destinations")
    seen: set[tuple[str, str, str]] = set()
    if isinstance(destinations, list):
        for i, dest in enumerate(destinations):
            if not isinstance(dest, dict):
                continue
            ref = dest.get("endpoint_ref")
            _check_ref(ref, f"/destinations/{i}/endpoint_ref")
            if isinstance(ref, dict):
                key = (
                    str(ref.get("scope")),
                    str(ref.get("connection_id")),
                    str(ref.get("alias")),
                )
                if key in seen:
                    findings.append(
                        finding(
                            "endpoint-ref-shape",
                            "error",
                            f"/destinations/{i}/endpoint_ref",
                            f"duplicate destination endpoint_ref {key!r}; refs must be unique by (scope, connection_id, alias).",
                            rule_doc="streams/stream-schema-parameterization.md#endpoint-refs",
                        )
                    )
                seen.add(key)
    return findings


# ---------------------------------------------------------------------------
# mapping-shape
# ---------------------------------------------------------------------------


def check_mapping_shape(doc: dict) -> list[dict]:
    findings: list[dict] = []
    mapping = doc.get("mapping")
    if not isinstance(mapping, dict):
        return findings
    assignments = mapping.get("assignments")
    if not isinstance(assignments, list):
        return findings
    seen_paths: dict[str, int] = {}
    for i, asn in enumerate(assignments):
        if not isinstance(asn, dict):
            continue
        target = asn.get("target")
        if isinstance(target, dict):
            path = target.get("path")
            if isinstance(path, str):
                if path in seen_paths:
                    findings.append(
                        finding(
                            "mapping-shape",
                            "error",
                            f"/mapping/assignments/{i}/target/path",
                            f"duplicate target.path {path!r}; previously declared at /mapping/assignments/{seen_paths[path]}.",
                            rule_doc="streams/stream-schema-parameterization.md#mapping",
                        )
                    )
                else:
                    seen_paths[path] = i
        value = asn.get("value")
        if isinstance(value, dict):
            has_expr = "expression" in value and value["expression"] is not None
            has_const = "constant" in value and value["constant"] is not None
            if has_expr == has_const:
                findings.append(
                    finding(
                        "mapping-shape",
                        "error",
                        f"/mapping/assignments/{i}/value",
                        "assignment.value must have exactly one of 'expression' or 'constant'.",
                        rule_doc="streams/stream-schema-parameterization.md#mapping",
                    )
                )
            if has_expr:
                expr = value["expression"]
                if isinstance(expr, dict):
                    op = expr.get("op")
                    if op != "get":
                        findings.append(
                            finding(
                                "mapping-shape",
                                "error",
                                f"/mapping/assignments/{i}/value/expression/op",
                                f"only expression.op='get' is supported in v1; got {op!r}.",
                                rule_doc="streams/stream-schema-parameterization.md#mapping",
                            )
                        )
        validate = asn.get("validate")
        if isinstance(validate, dict):
            rules = validate.get("rules")
            if isinstance(rules, list):
                for j, rule in enumerate(rules):
                    if not isinstance(rule, dict):
                        continue
                    field = rule.get("field")
                    if isinstance(field, str) and field not in seen_paths and field not in {
                        a.get("target", {}).get("path")
                        for a in assignments
                        if isinstance(a, dict) and isinstance(a.get("target"), dict)
                    }:
                        findings.append(
                            finding(
                                "mapping-shape",
                                "error",
                                f"/mapping/assignments/{i}/validate/rules/{j}/field",
                                f"validate.rules[{j}].field {field!r} does not match any assignment target.path.",
                                rule_doc="streams/stream-schema-parameterization.md#mapping",
                            )
                        )
    return findings


# ---------------------------------------------------------------------------
# filter-operators
# ---------------------------------------------------------------------------


def check_filter_operators(doc: dict) -> list[dict]:
    findings: list[dict] = []
    source = doc.get("source")
    if not isinstance(source, dict):
        return findings
    filters = source.get("filters")
    if not isinstance(filters, list):
        return findings
    scope = ((source.get("endpoint_ref") or {}).get("scope") if isinstance(source.get("endpoint_ref"), dict) else None)
    if scope == "connection":
        allowed = DB_FILTER_OPERATORS
        side = "database"
    elif scope == "connector":
        allowed = API_FILTER_OPERATORS
        side = "API"
    else:
        allowed = DB_FILTER_OPERATORS | API_FILTER_OPERATORS
        side = "either"
    for i, flt in enumerate(filters):
        if not isinstance(flt, dict):
            continue
        op = flt.get("operator")
        path = f"/source/filters/{i}"
        if isinstance(op, str) and op not in allowed:
            findings.append(
                finding(
                    "filter-operators",
                    "error",
                    f"{path}/operator",
                    f"operator {op!r} is not in the {side} operator vocabulary {sorted(allowed)}.",
                    rule_doc="shared/filter-operators.md",
                )
            )
        if isinstance(op, str) and op in UNARY_OPERATORS and "value" in flt:
            findings.append(
                finding(
                    "filter-operators",
                    "error",
                    f"{path}/value",
                    f"unary operator {op!r} must omit 'value'.",
                    rule_doc="shared/filter-operators.md",
                )
            )
        if isinstance(op, str) and op not in UNARY_OPERATORS and "value" not in flt:
            findings.append(
                finding(
                    "filter-operators",
                    "error",
                    f"{path}/value",
                    f"non-unary operator {op!r} requires 'value'.",
                    rule_doc="shared/filter-operators.md",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# secret-ref-format
# ---------------------------------------------------------------------------


def check_secret_ref_format(doc: dict) -> list[dict]:
    findings: list[dict] = []
    refs = doc.get("secret_refs")
    if not isinstance(refs, dict):
        return findings
    for key, value in refs.items():
        path = f"/secret_refs/{key}"
        if not isinstance(value, str):
            findings.append(
                finding(
                    "secret-ref-format",
                    "error",
                    path,
                    f"secret_refs.{key} must be a string; got {type(value).__name__}.",
                    rule_doc="connections/connection-schema-parameterization.md#secret-references",
                )
            )
            continue
        if not any(p.match(value) for p in SECRET_REF_PATTERNS):
            findings.append(
                finding(
                    "secret-ref-format",
                    "error",
                    path,
                    (
                        f"secret_refs.{key}={value!r} does not match any allowed prefix "
                        "(secrets/…, connections/…, ssm:/…, arn:aws:secretsmanager:…:secret:…, "
                        "arn:aws:ssm:…:parameter/…, s3://bucket/…)."
                    ),
                    rule_doc="connections/connection-schema-parameterization.md#secret-references",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# column-uniqueness
# ---------------------------------------------------------------------------


def check_column_uniqueness(doc: dict) -> list[dict]:
    findings: list[dict] = []
    columns = doc.get("columns")
    if not isinstance(columns, list):
        return findings
    names: dict[str, int] = {}
    positions: dict[int, int] = {}
    for i, col in enumerate(columns):
        if not isinstance(col, dict):
            continue
        name = col.get("name")
        if isinstance(name, str):
            if name in names:
                findings.append(
                    finding(
                        "column-uniqueness",
                        "error",
                        f"/columns/{i}/name",
                        f"column name {name!r} duplicated; previously declared at /columns/{names[name]}.",
                        rule_doc="endpoints/database-endpoint-schema-parameterization.md#columns",
                    )
                )
            else:
                names[name] = i
        pos = col.get("ordinal_position")
        if isinstance(pos, int):
            if pos in positions:
                findings.append(
                    finding(
                        "column-uniqueness",
                        "error",
                        f"/columns/{i}/ordinal_position",
                        f"ordinal_position {pos} duplicated; previously at /columns/{positions[pos]}.",
                        rule_doc="endpoints/database-endpoint-schema-parameterization.md#columns",
                    )
                )
            else:
                positions[pos] = i
    pks = doc.get("primary_keys")
    if isinstance(pks, list):
        for i, pk in enumerate(pks):
            if isinstance(pk, str) and pk not in names:
                findings.append(
                    finding(
                        "column-uniqueness",
                        "error",
                        f"/primary_keys/{i}",
                        f"primary_keys[{i}]={pk!r} does not reference any column.name.",
                        rule_doc="endpoints/database-endpoint-schema-parameterization.md#columns",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# pipeline-stream-consistency (requires --bundle-root)
# ---------------------------------------------------------------------------


def _stream_files_for_pipeline(
    bundle_root: Path,
    pipeline_alias: str | None,
) -> list[Path]:
    """Return the stream files that belong to this pipeline.

    Scopes the lookup to `bundle_root/pipelines/{alias}/streams/*.json` so a
    bundle containing several pipelines doesn't cause this pipeline to validate
    against sibling pipelines' streams. Falls back to `bundle_root/streams/`
    when the conventional layout isn't present (the user passed the pipeline
    directory directly as the bundle root).
    """
    if not isinstance(pipeline_alias, str) or not pipeline_alias:
        return []
    scoped = bundle_root / "pipelines" / pipeline_alias / "streams"
    if scoped.is_dir():
        return sorted(scoped.glob("*.json"))
    fallback = bundle_root / "streams"
    if fallback.is_dir():
        return sorted(fallback.glob("*.json"))
    return []


def _load_stream_files(
    stream_files: list[Path],
    findings: list[dict],
    validator_id: str,
) -> list[tuple[Path, dict]]:
    """Read + parse stream files. Emits a finding per failure rather than skipping."""
    out: list[tuple[Path, dict]] = []
    for sf in stream_files:
        try:
            raw = sf.read_text()
        except OSError as exc:
            findings.append(
                finding(
                    validator_id,
                    "error",
                    "/streams",
                    f"cannot read stream file {sf.name}: {exc}",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                )
            )
            continue
        except UnicodeDecodeError as exc:
            findings.append(
                finding(
                    validator_id,
                    "error",
                    "/streams",
                    f"stream file {sf.name} is not UTF-8: {exc}",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                )
            )
            continue
        try:
            sdoc = json.loads(raw)
        except json.JSONDecodeError as exc:
            findings.append(
                finding(
                    validator_id,
                    "error",
                    "/streams",
                    f"stream file {sf.name} is not valid JSON: {exc.msg} at line {exc.lineno} col {exc.colno}",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                )
            )
            continue
        if not isinstance(sdoc, dict):
            findings.append(
                finding(
                    validator_id,
                    "error",
                    "/streams",
                    f"stream file {sf.name} root must be a JSON object; got {type(sdoc).__name__}.",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                )
            )
            continue
        out.append((sf, sdoc))
    return out


def check_pipeline_stream_consistency(doc: dict, bundle_root: Path | None) -> list[dict]:
    findings: list[dict] = []
    streams_listed = doc.get("streams") or []
    if not isinstance(streams_listed, list) or not streams_listed:
        return findings
    if bundle_root is None:
        return [
            finding(
                "pipeline-stream-consistency",
                "warning",
                "/streams",
                "pipeline-stream cross-doc consistency not checked; pass --bundle-root to "
                "verify stream files match pipeline references.",
                rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
            )
        ]
    pipeline_alias = doc.get("alias")
    connections = doc.get("connections") or {}
    source_id = connections.get("source") if isinstance(connections, dict) else None
    dest_ids = connections.get("destinations") if isinstance(connections, dict) else None
    dest_set = set(dest_ids) if isinstance(dest_ids, list) else set()

    stream_files = _stream_files_for_pipeline(bundle_root, pipeline_alias)
    streams_by_alias: dict[str, tuple[Path, dict]] = {}
    for sf, sdoc in _load_stream_files(stream_files, findings, "pipeline-stream-consistency"):
        alias = sdoc.get("alias")
        if isinstance(alias, str):
            streams_by_alias[alias] = (sf, sdoc)

    # Match streams to files by `pipeline_id` — which is the pipeline's alias.
    for sf, sdoc in streams_by_alias.values():
        spid = sdoc.get("pipeline_id")
        if isinstance(pipeline_alias, str) and isinstance(spid, str) and spid != pipeline_alias:
            findings.append(
                finding(
                    "pipeline-stream-consistency",
                    "error",
                    "/streams",
                    f"stream file {sf.name} has pipeline_id {spid!r} which does not match "
                    f"pipeline.alias ({pipeline_alias!r}).",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#stream-pinning",
                )
            )
        src_ref = (sdoc.get("source") or {}).get("endpoint_ref") if isinstance(sdoc.get("source"), dict) else None
        if isinstance(src_ref, dict):
            scid = src_ref.get("connection_id")
            if isinstance(source_id, str) and scid != source_id:
                findings.append(
                    finding(
                        "pipeline-stream-consistency",
                        "error",
                        "/connections/source",
                        f"stream file {sf.name} source.endpoint_ref.connection_id={scid!r} does not "
                        f"match pipeline.connections.source={source_id!r}.",
                        rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                    )
                )
        dests = sdoc.get("destinations")
        if isinstance(dests, list):
            for j, dest in enumerate(dests):
                if not isinstance(dest, dict):
                    continue
                dref = dest.get("endpoint_ref")
                if isinstance(dref, dict):
                    dcid = dref.get("connection_id")
                    if isinstance(dcid, str) and dest_set and dcid not in dest_set:
                        findings.append(
                            finding(
                                "pipeline-stream-consistency",
                                "error",
                                "/connections/destinations",
                                f"stream file {sf.name} destinations[{j}].endpoint_ref.connection_id="
                                f"{dcid!r} is not in pipeline.connections.destinations.",
                                rule_doc="pipelines/pipeline-schema-parameterization.md#cross-doc-consistency",
                            )
                        )
    return findings


# ---------------------------------------------------------------------------
# status-lifecycle
# ---------------------------------------------------------------------------


def check_status_lifecycle(doc: dict, bundle_root: Path | None) -> list[dict]:
    findings: list[dict] = []
    status = doc.get("status", "draft")
    if status != "active":
        return findings
    streams_listed = doc.get("streams") or []
    if not isinstance(streams_listed, list) or len(streams_listed) == 0:
        findings.append(
            finding(
                "status-lifecycle",
                "error",
                "/status",
                "pipeline.status='active' requires at least one stream reference in /streams.",
                rule_doc="shared/lifecycle-status.md",
            )
        )
        return findings
    if bundle_root is None:
        findings.append(
            finding(
                "status-lifecycle",
                "warning",
                "/status",
                "pipeline.status='active' requires at least one referenced stream with status='active'; "
                "pass --bundle-root to verify across stream files.",
                rule_doc="shared/lifecycle-status.md",
            )
        )
        return findings
    pipeline_alias = doc.get("alias")
    stream_files = _stream_files_for_pipeline(bundle_root, pipeline_alias)
    any_active = False
    for _, sdoc in _load_stream_files(stream_files, findings, "status-lifecycle"):
        if sdoc.get("status") == "active":
            any_active = True
            break
    if not any_active:
        findings.append(
            finding(
                "status-lifecycle",
                "error",
                "/status",
                "pipeline.status='active' but no referenced stream file has status='active'.",
                rule_doc="shared/lifecycle-status.md",
            )
        )
    return findings


# ---------------------------------------------------------------------------
# Validator dispatch by entity
# ---------------------------------------------------------------------------


def run_semantic_validators(
    doc: dict,
    entity: str,
    bundle_root: Path | None = None,
) -> list[dict]:
    findings: list[dict] = []
    findings.extend(check_reserved_fields(doc, entity))
    if entity == "pipeline":
        findings.extend(check_schedule_shape(doc))
        findings.extend(check_runtime_ranges(doc))
        findings.extend(check_pipeline_stream_consistency(doc, bundle_root))
        findings.extend(check_status_lifecycle(doc, bundle_root))
    elif entity == "stream":
        findings.extend(check_endpoint_ref_shape(doc))
        findings.extend(check_mapping_shape(doc))
        findings.extend(check_filter_operators(doc))
    elif entity == "connection":
        findings.extend(check_secret_ref_format(doc))
    elif entity == "database_endpoint":
        findings.extend(check_column_uniqueness(doc))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _emit(findings: list[dict]) -> int:
    """Print Diagnostics JSON and return the appropriate exit code."""
    passed = all(f["severity"] != "error" for f in findings)
    print(json.dumps({"passed": passed, "findings": findings}, indent=2))
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an Analitiq pipeline / stream / connection / database-endpoint document.")
    parser.add_argument(
        "--entity",
        required=True,
        choices=sorted(ENTITY_SCHEMAS.keys()),
        help="Which entity type the document represents (selects the default schema).",
    )
    parser.add_argument("--document", required=True, help="Path to JSON document to validate.")
    parser.add_argument("--bundle-root", help="Project root for cross-document semantic validation.")
    parser.add_argument("--schema-url", help="Override the default schema URL for --entity.")
    parser.add_argument("--semantic-only", action="store_true", help="Skip Layer 1 JSON Schema validation.")
    parser.add_argument("--json-only", action="store_true", help="Skip Layer 2 semantic validators.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass schema disk cache.")
    args = parser.parse_args()

    if args.semantic_only and args.json_only:
        parser.error("--semantic-only and --json-only are mutually exclusive (would skip all validation).")

    schema_url = args.schema_url or ENTITY_SCHEMAS[args.entity]
    document_path = Path(args.document)

    bundle_root: Path | None = None
    if args.bundle_root:
        bundle_root = Path(args.bundle_root).resolve()
        if not bundle_root.is_dir():
            return _emit([
                finding("json-schema", "error", "",
                        f"--bundle-root {bundle_root} is not an existing directory.")
            ])

    # Read + parse the document. Each failure mode gets its own diagnostic.
    try:
        raw = document_path.read_text()
    except FileNotFoundError:
        return _emit([finding("json-schema", "error", "",
                              f"Document not found: {document_path}")])
    except (PermissionError, IsADirectoryError, OSError) as exc:
        return _emit([finding("json-schema", "error", "",
                              f"Cannot read document {document_path}: {exc}")])
    except UnicodeDecodeError as exc:
        return _emit([finding("json-schema", "error", "",
                              f"Document {document_path} is not UTF-8: {exc}")])

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _emit([finding("json-schema", "error", "",
                              f"Document {document_path} is not valid JSON: "
                              f"{exc.msg} at line {exc.lineno} col {exc.colno}")])

    if not isinstance(document, dict):
        return _emit([finding("json-schema", "error", "",
                              f"Document root must be a JSON object; got {type(document).__name__}.")])

    findings: list[dict] = []

    # Layer 1 fetch + validation. Fetch failure records a finding but does
    # NOT short-circuit Layer 2 — semantic validators don't depend on the
    # schema and would otherwise be wastefully gated on a transient network
    # blip.
    if not args.semantic_only:
        schema: dict | None = None
        try:
            schema = fetch_schema(schema_url, cache=not args.no_cache)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, OSError, RuntimeError) as exc:
            findings.append(
                finding(
                    "json-schema", "error", "",
                    f"Cannot fetch schema {schema_url}: {exc}. Layer 1 skipped; "
                    "re-run with connectivity or use --semantic-only to suppress.",
                )
            )
        if schema is not None:
            findings.extend(layer1_jsonschema(document, schema, args.entity))

    if not args.json_only:
        findings.extend(run_semantic_validators(document, args.entity, bundle_root=bundle_root))

    return _emit(findings)


if __name__ == "__main__":
    sys.exit(main())
