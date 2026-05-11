#!/usr/bin/env python3
"""Validate an Analitiq pipeline, stream, connection, or database-endpoint document.

Layer 1: JSON Schema validation against the published schema URL (Draft 2020-12).
Layer 2: Semantic validators encoding rules that JSON Schema can't express.

Output: a single Diagnostics JSON object on stdout. Exit 0 iff `passed` is true.

The fetch URL (--schema-url) and the document's own `$schema` field are
deliberately decoupled: schemas are served from the dev host
(schemas.analitiq.work) while authored documents declare the production
host (schemas.analitiq.ai) — the `$schema` const inside each schema
locks that.
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
from typing import Any, Callable

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
except ImportError:  # Python < 3.9 — not supported by the plugin but fail clean
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Schema fetch + cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "analitiq" / "schemas"

ENTITY_SCHEMAS = {
    "pipeline": "https://schemas.analitiq.work/pipeline/latest.json",
    "stream": "https://schemas.analitiq.work/stream/latest.json",
    "connection": "https://schemas.analitiq.work/connection/latest.json",
    "database_endpoint": "https://schemas.analitiq.work/database-endpoint/latest.json",
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
    tmp_path.write_text(body)
    os.replace(tmp_path, cache_path)
    return schema


# ---------------------------------------------------------------------------
# Diagnostics helpers
# ---------------------------------------------------------------------------

VALIDATOR_IDS = {
    "json-schema",
    "reserved-field",
    "versioned-id-format",
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
    """Return a shallow-cloned schema with server-managed fields removed from `required`.

    The published pipeline/stream/connection schemas describe the canonical
    server-stamped document, so they mark fields like `pipeline_id`, `version`,
    `org_id`, `created_at`, `updated_at` as required at the JSON Schema level.
    Authored documents intentionally omit those fields (the registry stamps
    them on insert). This helper drops just those entries from the top-level
    `required` array so authored documents can pass Layer 1; the
    `reserved-field` Layer 2 validator still catches the inverse case (an
    authored doc that *does* contain a server-managed field).
    """
    server_fields = RESERVED_FIELDS_BY_ENTITY.get(entity, set())
    if not server_fields or "required" not in schema:
        return schema
    cloned = dict(schema)
    cloned["required"] = [r for r in schema["required"] if r not in server_fields]
    return cloned


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
        "pipeline_schema_version",
        "org_id",
        "created_at",
        "updated_at",
    },
    "stream": {
        "stream_id",
        "version",
        "stream_schema_version",
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
        "connection_schema_version",
        "org_id",
        "connector_id",
        "connector_version",
        "auth_state",
        "created_at",
        "updated_at",
    },
    "database_endpoint": {
        "endpoint_id",
        "endpoint_schema_version",
        "connector_id",
        "connector_version",
        "connection_id",
        "schema_hash",
    },
}


VERSIONED_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}_v[1-9][0-9]*$"
)
BASE_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
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


# ---------------------------------------------------------------------------
# reserved-field
# ---------------------------------------------------------------------------


def check_reserved_fields(doc: dict, entity: str) -> list[dict]:
    reserved = RESERVED_FIELDS_BY_ENTITY.get(entity, set())
    findings: list[dict] = []
    for field in sorted(reserved):
        if field in doc:
            findings.append(
                finding(
                    "reserved-field",
                    "error",
                    f"/{field}",
                    f"Reserved server-managed field '{field}' must not appear in authored {entity} documents.",
                    rule_doc=f"{entity}s/{entity}-schema-parameterization.md#server-managed-and-reserved-fields",
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
                    rule_doc="streams/stream-schema-parameterization.md#server-managed-and-reserved-fields",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# versioned-id-format
# ---------------------------------------------------------------------------


def _check_versioned_id(value: Any, path: str) -> list[dict]:
    findings: list[dict] = []
    if not isinstance(value, str):
        findings.append(
            finding(
                "versioned-id-format",
                "error",
                path,
                f"expected a versioned ID string of the form <uuid>_v<n>; got {type(value).__name__}.",
                rule_doc="shared/identity-and-versioning.md",
            )
        )
        return findings
    if not VERSIONED_ID_RE.match(value):
        findings.append(
            finding(
                "versioned-id-format",
                "error",
                path,
                f"value {value!r} does not match versioned-id pattern <uuid>_v<positive integer>.",
                rule_doc="shared/identity-and-versioning.md",
            )
        )
    return findings


def check_versioned_ids_pipeline(doc: dict) -> list[dict]:
    findings: list[dict] = []
    connections = doc.get("connections")
    if isinstance(connections, dict):
        source = connections.get("source")
        if source is not None:
            findings.extend(_check_versioned_id(source, "/connections/source"))
        destinations = connections.get("destinations")
        if isinstance(destinations, list):
            for i, dest in enumerate(destinations):
                findings.extend(_check_versioned_id(dest, f"/connections/destinations/{i}"))
    streams = doc.get("streams")
    if isinstance(streams, list):
        for i, sid in enumerate(streams):
            findings.extend(_check_versioned_id(sid, f"/streams/{i}"))
    return findings


def check_versioned_ids_stream(doc: dict) -> list[dict]:
    findings: list[dict] = []
    pipeline_id = doc.get("pipeline_id")
    if pipeline_id is not None:
        if not isinstance(pipeline_id, str) or not BASE_UUID_RE.match(pipeline_id):
            findings.append(
                finding(
                    "versioned-id-format",
                    "error",
                    "/pipeline_id",
                    f"stream.pipeline_id must be a base UUID (no _v suffix); got {pipeline_id!r}.",
                    rule_doc="shared/identity-and-versioning.md",
                )
            )
    source_ref = (doc.get("source") or {}).get("endpoint_ref") if isinstance(doc.get("source"), dict) else None
    if isinstance(source_ref, dict) and "connection_id" in source_ref:
        findings.extend(
            _check_versioned_id(source_ref["connection_id"], "/source/endpoint_ref/connection_id")
        )
    destinations = doc.get("destinations")
    if isinstance(destinations, list):
        for i, dest in enumerate(destinations):
            if not isinstance(dest, dict):
                continue
            ref = dest.get("endpoint_ref")
            if isinstance(ref, dict) and "connection_id" in ref:
                findings.extend(
                    _check_versioned_id(
                        ref["connection_id"], f"/destinations/{i}/endpoint_ref/connection_id"
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
    if isinstance(tz, str) and ZoneInfo is not None:
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

    def _check_ref(ref: Any, path: str, side: str) -> None:
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
        _check_ref(source.get("endpoint_ref"), "/source/endpoint_ref", "source")
    destinations = doc.get("destinations")
    seen: set[tuple[str, str, str]] = set()
    if isinstance(destinations, list):
        for i, dest in enumerate(destinations):
            if not isinstance(dest, dict):
                continue
            ref = dest.get("endpoint_ref")
            _check_ref(ref, f"/destinations/{i}/endpoint_ref", "destination")
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


def _strip_version(versioned: str) -> str | None:
    if not isinstance(versioned, str):
        return None
    m = re.match(r"^(.+)_v[1-9][0-9]*$", versioned)
    return m.group(1) if m else None


def _find_stream_files(bundle_root: Path) -> list[Path]:
    return sorted(bundle_root.rglob("streams/*.json"))


def check_pipeline_stream_consistency(doc: dict, bundle_root: Path | None) -> list[dict]:
    findings: list[dict] = []
    if bundle_root is None:
        return findings
    streams_listed = doc.get("streams") or []
    if not isinstance(streams_listed, list) or not streams_listed:
        return findings
    pipeline_alias = doc.get("alias")
    connections = doc.get("connections") or {}
    source_id = connections.get("source") if isinstance(connections, dict) else None
    dest_ids = connections.get("destinations") if isinstance(connections, dict) else None
    dest_set = set(dest_ids) if isinstance(dest_ids, list) else set()

    stream_files = _find_stream_files(bundle_root)
    streams_by_id: dict[str, dict] = {}
    streams_by_alias: dict[str, tuple[Path, dict]] = {}
    for sf in stream_files:
        try:
            sdoc = json.loads(sf.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(sdoc, dict):
            continue
        alias = sdoc.get("alias")
        if isinstance(alias, str):
            streams_by_alias[alias] = (sf, sdoc)

    base_uuids_seen: dict[str, str] = {}
    for i, sid in enumerate(streams_listed):
        if not isinstance(sid, str):
            continue
        base = _strip_version(sid)
        if base in base_uuids_seen:
            findings.append(
                finding(
                    "pipeline-stream-consistency",
                    "error",
                    f"/streams/{i}",
                    f"stream base UUID {base!r} appears more than once in pipeline.streams "
                    f"(also at {base_uuids_seen[base]}).",
                    rule_doc="pipelines/pipeline-schema-parameterization.md#stream-pinning",
                )
            )
        elif base is not None:
            base_uuids_seen[base] = f"/streams/{i}"

    # Match streams to files by `pipeline_id` (base UUID) — when we can find one.
    pipeline_base = _strip_version(_synthetic_pipeline_id(pipeline_alias)) if pipeline_alias else None
    for sf, sdoc in streams_by_alias.values():
        spid = sdoc.get("pipeline_id")
        if pipeline_base is not None and isinstance(spid, str) and spid != pipeline_base:
            findings.append(
                finding(
                    "pipeline-stream-consistency",
                    "warning",
                    "/streams",
                    f"stream file {sf.name} has pipeline_id {spid!r} which does not match the placeholder "
                    f"derived from pipeline.alias ({pipeline_base!r}). If you supply your own pipeline_id, "
                    "ensure stream files match.",
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


def _synthetic_pipeline_id(alias: str) -> str:
    """Mint the deterministic placeholder versioned ID the orchestrator uses for a pipeline."""
    import uuid
    base = uuid.uuid5(uuid.NAMESPACE_URL, f"analitiq:pipeline:{alias}")
    return f"{base}_v1"


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
    any_active = False
    for sf in _find_stream_files(bundle_root):
        try:
            sdoc = json.loads(sf.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(sdoc, dict) and sdoc.get("status") == "active":
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
        findings.extend(check_versioned_ids_pipeline(doc))
        findings.extend(check_schedule_shape(doc))
        findings.extend(check_runtime_ranges(doc))
        findings.extend(check_pipeline_stream_consistency(doc, bundle_root))
        findings.extend(check_status_lifecycle(doc, bundle_root))
    elif entity == "stream":
        findings.extend(check_versioned_ids_stream(doc))
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
    bundle_root = Path(args.bundle_root).resolve() if args.bundle_root else None

    try:
        document = json.loads(document_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "passed": False,
                    "findings": [
                        finding("json-schema", "error", "", f"Cannot read document: {exc}")
                    ],
                }
            )
        )
        return 1

    findings: list[dict] = []

    if not args.semantic_only:
        try:
            schema = fetch_schema(schema_url, cache=not args.no_cache)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
            print(
                json.dumps(
                    {
                        "passed": False,
                        "findings": [
                            finding("json-schema", "error", "", f"Cannot fetch schema {schema_url}: {exc}")
                        ],
                    }
                )
            )
            return 1
        findings.extend(layer1_jsonschema(document, schema, args.entity))

    if not args.json_only:
        findings.extend(run_semantic_validators(document, args.entity, bundle_root=bundle_root))

    passed = all(f["severity"] != "error" for f in findings)
    print(json.dumps({"passed": passed, "findings": findings}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
