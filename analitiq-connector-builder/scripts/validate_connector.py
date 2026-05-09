#!/usr/bin/env python3
"""Validate an Analitiq connector or endpoint document.

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


# ---------------------------------------------------------------------------
# Schema fetch + cache
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "analitiq" / "schemas"


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
    "expression-resolver",
    "phase-resolvability",
    "transport-ref",
    "dsn-binding",
    "auth-shape",
    "tls-consistency",
    "type-map-coverage",
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


def layer1_jsonschema(document: dict, schema: dict) -> list[dict]:
    """Run Draft 2020-12 validation, mapping each error to a finding."""
    validator = Draft202012Validator(schema)
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

RESERVED_FIELDS = {
    "connector_id",
    "connector_schema_version",
    "created_at",
    "updated_at",
}

KNOWN_SCOPES = {
    "secrets",
    "connection.parameters",
    "connection.selections",
    "connection.discovered",
    "auth",
    "runtime",
    "stream",
}

KNOWN_FUNCTIONS = {
    "basic_auth",
    "jwt_sign",
    "url_encode",
}

KNOWN_ENCODINGS = {
    "raw",
    "host",
    "url_userinfo",
    "url_path_segment",
    "url_query_key",
    "url_query_value",
}


def check_reserved_fields(doc: dict) -> list[dict]:
    findings = []
    for field in RESERVED_FIELDS:
        if field in doc:
            findings.append(
                finding(
                    "reserved-field",
                    "error",
                    f"/{field}",
                    f"Reserved server-managed field '{field}' must not appear in authored documents.",
                    rule_doc="connectors/connector-schema-parameterization.md#server-managed-and-reserved-fields",
                )
            )
    return findings


def _walk(node: Any, path: str = ""):
    """Yield (path, node) pairs for every nested object in the document."""
    if isinstance(node, dict):
        yield path or "/", node
        for k, v in node.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}/{i}")


def _is_value_expression(node: Any) -> str | None:
    """Return the expression kind ('ref'/'template'/'literal'/'function') or None."""
    if not isinstance(node, dict):
        return None
    keys = set(node.keys())
    if "ref" in keys and isinstance(node["ref"], str):
        return "ref"
    if "template" in keys and isinstance(node["template"], str):
        return "template"
    if "literal" in keys:
        return "literal"
    if "function" in keys and isinstance(node["function"], str):
        return "function"
    return None


_SINGLE_TOKEN_SCOPES = {s for s in KNOWN_SCOPES if "." not in s}
_MULTI_TOKEN_SCOPE_HEADS = {s.split(".", 1)[0] for s in KNOWN_SCOPES if "." in s}


def _scope_is_known(dotted: str) -> bool:
    """Decide whether a dotted path targets a known scope.

    For single-token scopes (`secrets`, `auth`, `runtime`, `stream`),
    the head alone is enough. For multi-token scope heads like
    `connection`, the *two-token* prefix must be one of the registered
    scopes — `connection.bogus.x` is rejected.
    """
    head_one = dotted.split(".", 1)[0]
    if head_one in _SINGLE_TOKEN_SCOPES:
        return True
    if head_one in _MULTI_TOKEN_SCOPE_HEADS:
        head_two = ".".join(dotted.split(".", 2)[:2])
        return head_two in KNOWN_SCOPES
    return False


def check_expressions(doc: dict) -> list[dict]:
    findings: list[dict] = []
    ref_pattern = re.compile(r"^([a-z_]+(?:\.[a-z_]+)*)(?:\.[A-Za-z0-9_-]+)*$")
    template_var = re.compile(r"\$\{([^}]+)\}")
    for path, node in _walk(doc):
        kind = _is_value_expression(node)
        if not kind:
            continue
        if kind == "ref":
            ref = node["ref"]
            scope_match = ref_pattern.match(ref)
            if not scope_match:
                findings.append(
                    finding(
                        "expression-resolver",
                        "error",
                        path,
                        f"ref '{ref}' is not a valid dotted path.",
                        rule_doc="shared/value-expression-parameterization.md",
                    )
                )
                continue
            if not _scope_is_known(ref):
                findings.append(
                    finding(
                        "expression-resolver",
                        "error",
                        path,
                        f"ref '{ref}' targets unknown scope. Known scopes: {sorted(KNOWN_SCOPES)}.",
                        rule_doc="shared/value-expression-parameterization.md",
                    )
                )
        elif kind == "template":
            for var in template_var.findall(node["template"]):
                if not _scope_is_known(var):
                    findings.append(
                        finding(
                            "expression-resolver",
                            "error",
                            path,
                            f"template variable '${{{var}}}' targets unknown scope.",
                            rule_doc="shared/value-expression-parameterization.md",
                        )
                    )
        elif kind == "function":
            fn = node["function"]
            if fn not in KNOWN_FUNCTIONS:
                findings.append(
                    finding(
                        "expression-resolver",
                        "error",
                        path,
                        f"function '{fn}' is not in the registered catalog: {sorted(KNOWN_FUNCTIONS)}.",
                        rule_doc="shared/value-expression-parameterization.md",
                    )
                )
    return findings


def check_transport_refs(doc: dict) -> list[dict]:
    findings: list[dict] = []
    transports = doc.get("transports", {})
    if not isinstance(transports, dict):
        findings.append(
            finding(
                "transport-ref",
                "error",
                "/transports",
                f"transports must be an object; got {type(transports).__name__}.",
                rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
            )
        )
        return findings
    transport_keys = set(transports.keys())
    default = doc.get("default_transport")
    if default is not None and default not in transport_keys:
        findings.append(
            finding(
                "transport-ref",
                "error",
                "/default_transport",
                f"default_transport '{default}' is not defined in transports {sorted(transport_keys)}.",
                rule_doc="connectors/connector-schema-parameterization.md#transport-selection",
            )
        )
    for path, node in _walk(doc):
        if isinstance(node, dict) and "transport_ref" in node and isinstance(node["transport_ref"], str):
            ref = node["transport_ref"]
            if ref not in transport_keys:
                findings.append(
                    finding(
                        "transport-ref",
                        "error",
                        f"{path}/transport_ref",
                        f"transport_ref '{ref}' is not defined in transports {sorted(transport_keys)}.",
                        rule_doc="connectors/connector-schema-parameterization.md#transport-selection",
                    )
                )
    return findings


def check_dsn_bindings(doc: dict) -> list[dict]:
    findings: list[dict] = []
    transports = doc.get("transports", {})
    if not isinstance(transports, dict):
        return findings  # `check_transport_refs` already emitted the structural error
    placeholder_re = re.compile(r"\{([^}]+)\}")
    for tname, tspec in transports.items():
        if not isinstance(tspec, dict):
            findings.append(
                finding(
                    "dsn-binding",
                    "error",
                    f"/transports/{tname}",
                    f"transport entry must be an object; got {type(tspec).__name__}.",
                    rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
                )
            )
            continue
        dsn = tspec.get("dsn")
        if not isinstance(dsn, dict) or dsn.get("kind") != "url_template":
            continue
        path_prefix = f"/transports/{tname}/dsn"
        template = dsn.get("template", "")
        bindings = dsn.get("bindings", {})
        placeholders = set(placeholder_re.findall(template))
        binding_keys = set(bindings.keys()) if isinstance(bindings, dict) else set()
        for ph in placeholders - binding_keys:
            findings.append(
                finding(
                    "dsn-binding",
                    "error",
                    f"{path_prefix}/template",
                    f"placeholder '{{{ph}}}' has no matching binding.",
                    rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
                )
            )
        for bk in binding_keys - placeholders:
            findings.append(
                finding(
                    "dsn-binding",
                    "warning",
                    f"{path_prefix}/bindings/{bk}",
                    f"binding '{bk}' is not referenced by the template.",
                    rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
                )
            )
        if isinstance(bindings, dict):
            for bk, bspec in bindings.items():
                if not isinstance(bspec, dict):
                    findings.append(
                        finding(
                            "dsn-binding",
                            "error",
                            f"{path_prefix}/bindings/{bk}",
                            f"binding must be an object with 'value' and 'encoding'; got {type(bspec).__name__}.",
                            rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
                        )
                    )
                    continue
                enc = bspec.get("encoding")
                if enc is not None and enc not in KNOWN_ENCODINGS:
                    findings.append(
                        finding(
                            "dsn-binding",
                            "error",
                            f"{path_prefix}/bindings/{bk}/encoding",
                            f"encoding '{enc}' is not in the closed enum {sorted(KNOWN_ENCODINGS)}.",
                            rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
                        )
                    )
    return findings


def check_auth_shape(doc: dict) -> list[dict]:
    findings: list[dict] = []
    auth = doc.get("auth")
    if not isinstance(auth, dict):
        return findings
    atype = auth.get("type")
    if atype == "oauth2_authorization_code":
        for required in ("authorize", "token_exchange"):
            if required not in auth:
                findings.append(
                    finding(
                        "auth-shape",
                        "error",
                        f"/auth/{required}",
                        f"oauth2_authorization_code requires '{required}'.",
                        rule_doc="connectors/connector-schema-parameterization.md#authentication",
                    )
                )
    elif atype == "oauth2_client_credentials":
        if "token_exchange" not in auth:
            findings.append(
                finding(
                    "auth-shape",
                    "error",
                    "/auth/token_exchange",
                    "oauth2_client_credentials requires 'token_exchange'.",
                    rule_doc="connectors/connector-schema-parameterization.md#authentication",
                )
            )
        if "authorize" in auth:
            findings.append(
                finding(
                    "auth-shape",
                    "error",
                    "/auth/authorize",
                    "oauth2_client_credentials must omit 'authorize'.",
                    rule_doc="connectors/connector-schema-parameterization.md#authentication",
                )
            )
    elif atype == "none":
        for forbidden in ("authorize", "token_exchange", "refresh"):
            if forbidden in auth:
                findings.append(
                    finding(
                        "auth-shape",
                        "error",
                        f"/auth/{forbidden}",
                        f"auth.type 'none' must not declare '{forbidden}'.",
                        rule_doc="connectors/connector-schema-parameterization.md#authentication",
                    )
                )
    return findings


def check_tls_consistency(doc: dict) -> list[dict]:
    findings: list[dict] = []
    inputs = doc.get("connection_contract", {}).get("inputs", {})
    if not isinstance(inputs, dict):
        return findings
    ssl_mode = inputs.get("ssl_mode", {})
    if not isinstance(ssl_mode, dict):
        return findings
    enum = ssl_mode.get("enum") or []
    requires_ca = any(v in {"verify-ca", "verify-full"} for v in enum)
    has_ca_input = "ssl_ca_certificate" in inputs
    if requires_ca and not has_ca_input:
        findings.append(
            finding(
                "tls-consistency",
                "error",
                "/connection_contract/inputs",
                "ssl_mode allows verify-ca/verify-full but ssl_ca_certificate input is not declared.",
                rule_doc="connectors/connector-schema-parameterization.md#transport-contracts",
            )
        )
    return findings


# Lifecycle phase ordering. Anything available in an earlier phase is also
# available in later ones. Index = phase rank (higher = later).
_PHASE_ORDER = ["pre_auth", "auth", "post_auth", "active"]


def _phase_le(a: str, b: str) -> bool:
    """Return True iff phase `a` is reachable in phase `b` (a runs no later than b)."""
    try:
        return _PHASE_ORDER.index(a) <= _PHASE_ORDER.index(b)
    except ValueError:
        return False


# Closed `runtime.*` set per `shared/lifecycle-phases.md`.
_GENERIC_RUNTIME_KEYS = {"run_id", "current_time", "batch_size"}
# Operation-local subkeys that can only be referenced inside an endpoint
# operation (request/response/pagination/cursor expressions). Connector-level
# templates cannot reach them. The validator does not currently walk endpoint
# operation templates, so any reference to these keys at the sites we *do*
# walk (transports, auth ops, post-auth ops) is an error.
_OPERATION_LOCAL_RUNTIME_KEYS = {"pagination"}
# `runtime.pagination.*` is itself a closed set per the spec.
_PAGINATION_RUNTIME_KEYS = {"offset"}
_OAUTH_RUNTIME_KEYS = {"code", "state", "redirect_uri", "pkce_verifier"}


def _index_inputs(doc: dict) -> dict[str, dict]:
    """Map storage-scoped reference path -> input record, for declared inputs.

    Keys are like `connection.parameters.host` and `secrets.password`.
    Values carry the `phase` so the resolvability check can assert it.
    """
    out: dict[str, dict] = {}
    inputs = doc.get("connection_contract", {}).get("inputs") or {}
    if not isinstance(inputs, dict):
        return out
    for name, spec in inputs.items():
        if not isinstance(spec, dict):
            continue
        storage = spec.get("storage")
        phase = spec.get("phase", "pre_auth")
        if storage in ("connection.parameters", "secrets"):
            out[f"{storage}.{name}"] = {"phase": phase, "input_name": name, "via": "input"}
    return out


def _index_post_auth_outputs(doc: dict) -> tuple[dict[str, dict], list[dict]]:
    """Map produced reference paths to their post-auth output, plus warnings.

    Returns (index, warnings). The index keys are the produced paths (e.g.
    `connection.discovered.api_domain`); values describe the producing
    output. Warnings catch malformed entries.
    """
    findings: list[dict] = []
    out: dict[str, dict] = {}
    post_auth = doc.get("connection_contract", {}).get("post_auth_outputs") or {}
    if not isinstance(post_auth, dict):
        return out, findings
    valid_storage = {"connection.discovered", "connection.selections", "secrets"}
    for name, spec in post_auth.items():
        if not isinstance(spec, dict):
            continue
        storage = spec.get("storage")
        value_path = spec.get("value_path")
        if storage not in valid_storage:
            findings.append(
                finding(
                    "phase-resolvability",
                    "warning",
                    f"/connection_contract/post_auth_outputs/{name}",
                    f"post_auth_outputs.{name} has unrecognized storage {storage!r}.",
                    rule_doc="shared/lifecycle-phases.md",
                )
            )
            continue
        if not isinstance(value_path, str) or not value_path.startswith(f"{storage}."):
            findings.append(
                finding(
                    "phase-resolvability",
                    "warning",
                    f"/connection_contract/post_auth_outputs/{name}",
                    (
                        f"post_auth_outputs.{name} declares storage={storage!r} "
                        f"but value_path is missing or does not start with '{storage}.': {value_path!r}"
                    ),
                    rule_doc="shared/lifecycle-phases.md",
                )
            )
            continue
        out[value_path] = {"storage": storage, "output_name": name}
    return out, findings


def _ref_phase_problem(
    dotted: str,
    phase: str,
    auth_op: str | None,
    auth_type: str | None,
    input_idx: dict[str, dict],
    output_idx: dict[str, dict],
) -> str | None:
    """Return a human-readable error for `dotted` referenced in `phase`, or None.

    Handles every top-level scope (`runtime`, `auth`, `stream`, `state`,
    `connection`, `secrets`) directly — no caller-side OR-chaining.

    `auth_op` is one of "authorize", "token_exchange", "refresh", or None.
    """
    head = dotted.split(".", 1)[0]
    if head == "runtime":
        return _runtime_phase_problem(dotted, auth_op, auth_type)
    if head == "auth":
        if not _phase_le("post_auth", phase):
            return f"'auth.*' is not available before post_auth (current phase: {phase})."
        return None
    if head == "stream":
        if not _phase_le("active", phase):
            return f"'stream.*' is only available in the active phase (current phase: {phase})."
        return None
    if head == "state":
        if not _phase_le("active", phase):
            return f"'state.*' is only available in the active phase (current phase: {phase})."
        return None
    if head in ("secrets", "connection"):
        return _connection_or_secrets_phase_problem(dotted, phase, input_idx, output_idx)
    return None


def _runtime_phase_problem(
    dotted: str,
    auth_op: str | None,
    auth_type: str | None,
) -> str | None:
    parts = dotted.split(".", 2)
    if len(parts) < 2:
        return "'runtime' must be followed by a key (e.g. 'runtime.run_id')."
    sub = parts[1]
    if sub in _GENERIC_RUNTIME_KEYS:
        return None  # generic runtime is always available
    if sub in _OPERATION_LOCAL_RUNTIME_KEYS:
        sub_key = parts[2].split(".", 1)[0] if len(parts) >= 3 else ""
        if sub == "pagination" and sub_key not in _PAGINATION_RUNTIME_KEYS:
            return (
                f"'runtime.pagination.{sub_key}' is not in the closed set "
                f"{sorted(_PAGINATION_RUNTIME_KEYS)}."
            )
        # The validator does not currently walk endpoint operation templates,
        # so any reference at sites we *do* walk is out-of-context.
        return (
            f"'runtime.{sub}.*' is operation-local; "
            "it can only be referenced inside an endpoint operation template."
        )
    if sub == "oauth":
        if auth_type != "oauth2_authorization_code":
            return (
                f"'runtime.oauth.*' is only available when auth.type is "
                f"'oauth2_authorization_code' (current: {auth_type!r})."
            )
        oauth_key = parts[2].split(".", 1)[0] if len(parts) >= 3 else ""
        if oauth_key not in _OAUTH_RUNTIME_KEYS:
            return f"'runtime.oauth.{oauth_key}' is not in the closed set {sorted(_OAUTH_RUNTIME_KEYS)}."
        if auth_op == "refresh":
            return "'runtime.oauth.*' must not be referenced inside auth.refresh."
        if oauth_key == "code" and auth_op != "token_exchange":
            return f"'runtime.oauth.code' is only available inside auth.token_exchange (current op: {auth_op!r})."
        if auth_op not in ("authorize", "token_exchange"):
            return "'runtime.oauth.*' is only available in auth.authorize and auth.token_exchange."
        return None
    return f"'runtime.{sub}' is not in the registered closed set."


def _connection_or_secrets_phase_problem(
    dotted: str,
    phase: str,
    input_idx: dict[str, dict],
    output_idx: dict[str, dict],
) -> str | None:
    """Resolve refs into connection.parameters / connection.* / secrets."""
    head = dotted.split(".", 1)[0]
    if head == "secrets":
        primary = ".".join(dotted.split(".", 2)[:2])  # `secrets.password`
        record = input_idx.get(primary)
        if record is not None:
            if not _phase_le(record["phase"], phase):
                return (
                    f"'{primary}' is declared in phase '{record['phase']}' "
                    f"and is not available in '{phase}'."
                )
            return None
        if primary in output_idx:
            if not _phase_le("post_auth", phase):
                return f"'{primary}' is produced post-auth and is not available in '{phase}'."
            return None
        return f"'{primary}' is not declared as an input nor produced by a post_auth_output."
    if head != "connection":
        return None
    sub = dotted.split(".", 2)
    if len(sub) < 2:
        return "'connection' must be followed by a sub-scope."
    scope = ".".join(sub[:2])  # `connection.parameters` etc
    primary = ".".join(sub[:3]) if len(sub) >= 3 else scope  # `connection.parameters.host`
    if scope == "connection.parameters":
        record = input_idx.get(primary)
        if record is None:
            return f"'{primary}' is not declared in connection_contract.inputs."
        if not _phase_le(record["phase"], phase):
            return (
                f"'{primary}' is declared in phase '{record['phase']}' "
                f"and is not available in '{phase}'."
            )
        return None
    if scope in ("connection.discovered", "connection.selections"):
        if not _phase_le("post_auth", phase):
            return f"'{scope}.*' is only available from post_auth onward (current phase: {phase})."
        if primary not in output_idx:
            return f"'{primary}' is not produced by any post_auth_output."
        return None
    return None


def _walk_refs_with_phase(
    container: Any,
    base_path: str,
    phase: str,
    auth_op: str | None,
    auth_type: str | None,
    input_idx: dict[str, dict],
    output_idx: dict[str, dict],
) -> list[dict]:
    """Walk a sub-tree, validating every ref/template var against the phase model."""
    findings: list[dict] = []
    template_var = re.compile(r"\$\{([^}]+)\}")
    for path, node in _walk(container, base_path):
        if not isinstance(node, dict):
            continue
        ref = node.get("ref")
        if isinstance(ref, str):
            problem = _ref_phase_problem(ref, phase, auth_op, auth_type, input_idx, output_idx)
            if problem:
                findings.append(
                    finding(
                        "phase-resolvability",
                        "error",
                        path,
                        f"ref '{ref}': {problem}",
                        rule_doc="shared/lifecycle-phases.md",
                    )
                )
        tmpl = node.get("template")
        if isinstance(tmpl, str):
            for var in template_var.findall(tmpl):
                problem = _ref_phase_problem(var, phase, auth_op, auth_type, input_idx, output_idx)
                if problem:
                    findings.append(
                        finding(
                            "phase-resolvability",
                            "error",
                            path,
                            f"template '${{{var}}}': {problem}",
                            rule_doc="shared/lifecycle-phases.md",
                        )
                    )
    return findings


def check_phase_resolvability(doc: dict) -> list[dict]:
    """Validate every templated reference against `shared/lifecycle-phases.md`.

    Builds two indexes — declared inputs (from connection_contract.inputs)
    and produced outputs (from connection_contract.post_auth_outputs) —
    then walks the document at known phase-anchored sites and asserts each
    ref/template var targets a scope available in that phase.

    Anchored sites and their phases:

    | Site | Phase | Auth-op context |
    |---|---|---|
    | `auth.authorize.*` | auth | authorize |
    | `auth.token_exchange.*` | auth | token_exchange |
    | `auth.refresh.*` | post_auth | refresh |
    | `auth.test.*` | active | None |
    | `connection_contract.post_auth_outputs.*.options_request` | post_auth | None |
    | `connection_contract.post_auth_outputs.*.discovery_request` | post_auth | None |
    | `transports.*` | varies — assumed `active` (most permissive) by default |

    `auth.refresh` is modeled at `post_auth`-equivalent scope availability
    (rather than the spec table's `auth` phase) because it runs *after*
    the in-flight authorization-code workflow has completed, so persisted
    `auth.access_token` / `auth.refresh_token` are accessible. The spec's
    "no runtime.oauth.* inside refresh" rule is preserved via the
    `auth_op="refresh"` context flag.

    For transports we conservatively validate against the `active` phase.
    Transport phase inference (assigning each transport its earliest
    phase based on which auth/discovery/data ops reference it) is a
    deeper analysis tracked separately.

    Also emits a warning when a `post_auth_outputs` entry is malformed
    (bad storage, missing/invalid value_path).
    """
    findings: list[dict] = []
    auth = doc.get("auth") or {}
    auth_type = auth.get("type") if isinstance(auth, dict) else None
    input_idx = _index_inputs(doc)
    output_idx, malformed = _index_post_auth_outputs(doc)
    findings.extend(malformed)

    # Auth ops. Phase assignment notes:
    # - authorize / token_exchange run in the auth phase proper.
    # - refresh runs *after* the in-flight authorization-code workflow has
    #   completed, so it has access to persisted auth state (auth.access_token,
    #   auth.refresh_token). We model that as post_auth-level scope
    #   availability while keeping the spec's "no runtime.oauth.* in refresh"
    #   rule via the auth_op context flag.
    # - test runs against an established connection; treat as active.
    if isinstance(auth, dict):
        for op_name, op_phase in [
            ("authorize", "auth"),
            ("token_exchange", "auth"),
            ("refresh", "post_auth"),
            ("test", "active"),
        ]:
            op = auth.get(op_name)
            if isinstance(op, dict):
                findings.extend(
                    _walk_refs_with_phase(
                        op,
                        f"/auth/{op_name}",
                        phase=op_phase,
                        auth_op=op_name if op_name != "test" else None,
                        auth_type=auth_type,
                        input_idx=input_idx,
                        output_idx=output_idx,
                    )
                )

    # Post-auth output ops
    post_auth = doc.get("connection_contract", {}).get("post_auth_outputs") or {}
    if isinstance(post_auth, dict):
        for name, spec in post_auth.items():
            if not isinstance(spec, dict):
                continue
            for op_name in ("options_request", "discovery_request"):
                op = spec.get(op_name)
                if isinstance(op, dict):
                    findings.extend(
                        _walk_refs_with_phase(
                            op,
                            f"/connection_contract/post_auth_outputs/{name}/{op_name}",
                            phase="post_auth",
                            auth_op=None,
                            auth_type=auth_type,
                            input_idx=input_idx,
                            output_idx=output_idx,
                        )
                    )

    # Transports — conservatively validated against the active phase.
    transports = doc.get("transports") or {}
    if isinstance(transports, dict):
        for tname, tspec in transports.items():
            if not isinstance(tspec, dict):
                continue
            findings.extend(
                _walk_refs_with_phase(
                    tspec,
                    f"/transports/{tname}",
                    phase="active",
                    auth_op=None,
                    auth_type=auth_type,
                    input_idx=input_idx,
                    output_idx=output_idx,
                )
            )

    return findings


def check_type_map_coverage(doc: dict, doc_path: Path | None = None) -> list[dict]:
    """Validate connector `type_maps` coverage.

    For database connectors: warn when `type_maps` is missing or has zero
    rules. Per-native coverage at the connector level is intentionally
    not enforced — the runtime reconciles native types via discovery
    against the actual user database.

    For API connectors with sibling endpoint files (under
    `<connector_dir>/endpoints/`): walk every endpoint document, collect
    every JSON Schema `(type, format)` pair from `response.schema`
    properties and from `params[*]`, and verify the connector's
    `type_maps` rules cover each one. The native-string convention is
    `format` if present, else `type` (e.g. `"uuid"`, `"date-time"`,
    `"integer"`, `"boolean"`). Coverage matches via `exact` or `regex`
    rules just like DB type maps.

    `doc_path` is the absolute path to the connector document on disk;
    used to locate the sibling `endpoints/` directory. When omitted,
    API endpoint coverage is skipped (the validator was invoked without
    a filesystem-anchored connector).
    """
    findings: list[dict] = []
    kind = doc.get("kind")
    tm = doc.get("type_maps")

    if kind == "database":
        if not _has_usable_rules(tm):
            findings.append(
                finding(
                    "type-map-coverage",
                    "warning",
                    "/type_maps",
                    "database connector has no usable type_maps rules; native types will not be mapped to canonical Arrow types.",
                    rule_doc="shared/type-maps.md",
                )
            )
        return findings

    if kind != "api":
        return findings

    if doc_path is None:
        return findings

    endpoint_dir = doc_path.parent / "endpoints"
    if not endpoint_dir.is_dir():
        return findings

    endpoint_files = sorted(endpoint_dir.glob("*.json"))
    if not endpoint_files:
        return findings

    natives: dict[str, list[str]] = {}  # native_string -> list of "endpoint_file:json_pointer" sites
    for ep_path in endpoint_files:
        try:
            ep_doc = json.loads(ep_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(
                finding(
                    "type-map-coverage",
                    "warning",
                    "/type_maps",
                    (
                        f"endpoint file '{ep_path.name}' could not be read or parsed ({exc}); "
                        "skipped from type-map coverage analysis. Validate the endpoint file "
                        "directly for the parse error."
                    ),
                    rule_doc="shared/type-maps.md",
                )
            )
            continue
        for native, json_pointer in _collect_endpoint_natives(ep_doc):
            natives.setdefault(native, []).append(f"{ep_path.name}{json_pointer}")

    if not natives:
        return findings

    rules = _extract_type_map_rules(tm)
    if not rules:
        findings.append(
            finding(
                "type-map-coverage",
                "warning",
                "/type_maps",
                (
                    f"api connector has {len(natives)} native types across endpoint files "
                    f"({sorted(natives.keys())}) but no type_maps rules to cover them."
                ),
                rule_doc="shared/type-maps.md",
            )
        )
        return findings

    for native, sites in sorted(natives.items()):
        if not _native_is_covered(native, rules):
            findings.append(
                finding(
                    "type-map-coverage",
                    "error",
                    "/type_maps",
                    (
                        f"native type {native!r} appears in endpoint(s) "
                        f"{sites[:3]}{' ...' if len(sites) > 3 else ''} "
                        f"but is not covered by any type_maps rule."
                    ),
                    rule_doc="shared/type-maps.md",
                )
            )
    return findings


def _extract_type_map_rules(tm: Any) -> list[dict]:
    """Pull the rule list out of a `type_maps` block, regardless of nesting."""
    if not isinstance(tm, dict):
        return []
    if isinstance(tm.get("rules"), list):
        return [r for r in tm["rules"] if isinstance(r, dict)]
    for v in tm.values():
        if isinstance(v, dict) and isinstance(v.get("rules"), list):
            return [r for r in v["rules"] if isinstance(r, dict)]
    return []


def _native_is_covered(native: str, rules: list[dict]) -> bool:
    """Return True iff at least one rule matches `native`."""
    for rule in rules:
        method = rule.get("method")
        rule_native = rule.get("native")
        if not isinstance(rule_native, str):
            continue
        if method == "exact" and rule_native == native:
            return True
        if method == "regex":
            try:
                if re.match(rule_native, native):
                    return True
            except re.error:
                continue
    return False


def _collect_endpoint_natives(endpoint_doc: dict) -> list[tuple[str, str]]:
    """Walk an api-endpoint document and yield (native_string, json_pointer).

    Sources:
    - operations.read.response.schema (JSON Schema, recursive into properties / items / *Of branches)
    - operations.read.params[*] and operations.write.params[*]
    """
    out: list[tuple[str, str]] = []
    operations = endpoint_doc.get("operations") or {}
    if not isinstance(operations, dict):
        return out
    for op_name in ("read", "write"):
        op = operations.get(op_name)
        if not isinstance(op, dict):
            continue
        # response.schema (read only — write usually has no records-style response)
        response = op.get("response")
        if isinstance(response, dict):
            schema = response.get("schema")
            if isinstance(schema, dict):
                _collect_natives_from_jsonschema(
                    schema, f"/operations/{op_name}/response/schema", out
                )
        # params
        params = op.get("params")
        if isinstance(params, dict):
            for pname, pspec in params.items():
                if not isinstance(pspec, dict):
                    continue
                native = _native_from_type_format(pspec.get("type"), pspec.get("format"))
                if native:
                    out.append((native, f"/operations/{op_name}/params/{pname}"))
    return out


def _native_from_type_format(t: Any, f: Any) -> str | None:
    """Apply the convention: native = format if present, else type.

    Returns None for `object` / `array` / `null` types — those are
    structural rather than terminal natives. The walker recurses into
    them via their `properties` / `items` / `*Of` branches instead.
    """
    if isinstance(f, str) and f:
        return f
    if isinstance(t, str) and t and t not in ("object", "array", "null"):
        return t
    return None


def _collect_natives_from_jsonschema(node: Any, pointer: str, out: list[tuple[str, str]]) -> None:
    """Recursively walk a JSON Schema, collecting (native, pointer) pairs at leaves."""
    if not isinstance(node, dict):
        return
    t = node.get("type")
    f = node.get("format")
    native = _native_from_type_format(t, f)
    if native:
        out.append((native, pointer))
    # Recurse: object → properties; array → items; oneOf/anyOf/allOf → branches
    props = node.get("properties")
    if isinstance(props, dict):
        for k, v in props.items():
            _collect_natives_from_jsonschema(v, f"{pointer}/properties/{k}", out)
    items = node.get("items")
    if isinstance(items, dict):
        _collect_natives_from_jsonschema(items, f"{pointer}/items", out)
    elif isinstance(items, list):
        for i, v in enumerate(items):
            _collect_natives_from_jsonschema(v, f"{pointer}/items/{i}", out)
    for combiner in ("oneOf", "anyOf", "allOf"):
        branches = node.get(combiner)
        if isinstance(branches, list):
            for i, branch in enumerate(branches):
                _collect_natives_from_jsonschema(branch, f"{pointer}/{combiner}/{i}", out)


def _has_usable_rules(tm: Any) -> bool:
    """Return True iff `tm` is a non-empty mapping with at least one rule."""
    return len(_extract_type_map_rules(tm)) > 0


SEMANTIC_VALIDATORS: dict[str, Callable[..., list[dict]]] = {
    "reserved-field": check_reserved_fields,
    "expression-resolver": check_expressions,
    "transport-ref": check_transport_refs,
    "dsn-binding": check_dsn_bindings,
    "auth-shape": check_auth_shape,
    "tls-consistency": check_tls_consistency,
    "phase-resolvability": check_phase_resolvability,
    "type-map-coverage": check_type_map_coverage,
}

# Validators that accept an optional `doc_path` second positional argument.
_PATH_AWARE_VALIDATORS = {"type-map-coverage"}


def is_connector_doc(doc: dict) -> bool:
    return "kind" in doc and isinstance(doc.get("transports"), dict)


def run_semantic_validators(doc: dict, doc_path: Path | None = None) -> list[dict]:
    findings: list[dict] = []
    for vid, fn in SEMANTIC_VALIDATORS.items():
        # Skip validators that don't apply to non-connector docs
        if vid in {"transport-ref", "dsn-binding", "auth-shape", "tls-consistency", "type-map-coverage"} and not is_connector_doc(doc):
            continue
        if vid in _PATH_AWARE_VALIDATORS:
            findings.extend(fn(doc, doc_path))
        else:
            findings.extend(fn(doc))
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an Analitiq connector or endpoint document.")
    parser.add_argument("--schema-url", required=True, help="Published schema URL to validate against.")
    parser.add_argument("--document", required=True, help="Path to JSON document to validate.")
    parser.add_argument("--semantic-only", action="store_true", help="Skip Layer 1 JSON Schema validation.")
    parser.add_argument("--json-only", action="store_true", help="Skip Layer 2 semantic validators.")
    parser.add_argument("--no-cache", action="store_true", help="Bypass schema disk cache.")
    args = parser.parse_args()

    if args.semantic_only and args.json_only:
        parser.error("--semantic-only and --json-only are mutually exclusive (would skip all validation).")

    document_path = Path(args.document)
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
            schema = fetch_schema(args.schema_url, cache=not args.no_cache)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
            print(
                json.dumps(
                    {
                        "passed": False,
                        "findings": [
                            finding("json-schema", "error", "", f"Cannot fetch schema {args.schema_url}: {exc}")
                        ],
                    }
                )
            )
            return 1
        findings.extend(layer1_jsonschema(document, schema))

    if not args.json_only:
        findings.extend(run_semantic_validators(document, doc_path=document_path.resolve()))

    passed = all(f["severity"] != "error" for f in findings)
    print(json.dumps({"passed": passed, "findings": findings}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
