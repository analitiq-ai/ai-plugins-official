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
import urllib.request
from pathlib import Path
from typing import Any, Callable

try:
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
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
                        "message": f"Missing dependency: {exc}. Install with `pip install jsonschema referencing`.",
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
    """Fetch a JSON schema from URL with disk cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode()).hexdigest()[:16]
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text())
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read().decode()
    cache_path.write_text(body)
    return json.loads(body)


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
            head_one = ref.split(".", 1)[0]
            head_two = ".".join(ref.split(".", 2)[:2])
            if head_one not in {s.split(".", 1)[0] for s in KNOWN_SCOPES} and head_two not in KNOWN_SCOPES:
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
                head_one = var.split(".", 1)[0]
                head_two = ".".join(var.split(".", 2)[:2])
                if head_one not in {s.split(".", 1)[0] for s in KNOWN_SCOPES} and head_two not in KNOWN_SCOPES:
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
        return findings
    placeholder_re = re.compile(r"\{([^}]+)\}")
    for tname, tspec in transports.items():
        if not isinstance(tspec, dict):
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


def check_phase_resolvability(doc: dict) -> list[dict]:
    """Lightweight check: refs in transports must target scopes resolvable in their phase.

    We don't have full lifecycle phase info per transport; we flag the
    common error of a transport using `connection.discovered.*` without
    a documented post-auth output that produces it.
    """
    findings: list[dict] = []
    contract = doc.get("connection_contract", {})
    post_auth = contract.get("post_auth_outputs") or {}
    discovered_keys = set()
    if isinstance(post_auth, dict):
        for out in post_auth.values():
            if isinstance(out, dict) and out.get("storage") == "connection.discovered":
                value_path = out.get("value_path")
                if isinstance(value_path, str) and value_path.startswith("connection.discovered."):
                    discovered_keys.add(value_path.split(".", 2)[2])
    transports = doc.get("transports") or {}
    for tname, tspec in transports.items() if isinstance(transports, dict) else []:
        for path, node in _walk({"t": tspec}, f"/transports/{tname}"):
            if not isinstance(node, dict):
                continue
            ref = node.get("ref")
            if isinstance(ref, str) and ref.startswith("connection.discovered."):
                key = ref.split(".", 2)[2].split(".", 1)[0]
                if key not in discovered_keys:
                    findings.append(
                        finding(
                            "phase-resolvability",
                            "error",
                            path,
                            (
                                f"transport '{tname}' references 'connection.discovered.{key}' "
                                "but no post-auth output produces it."
                            ),
                            rule_doc="shared/lifecycle-phases.md",
                        )
                    )
    return findings


def check_type_map_coverage(doc: dict) -> list[dict]:
    """Stub — full coverage check requires shared/type-maps.md spec wiring.

    For now we warn on empty type_maps for database connectors.
    """
    findings: list[dict] = []
    if doc.get("kind") != "database":
        return findings
    tm = doc.get("type_maps")
    if tm is None or tm == {}:
        findings.append(
            finding(
                "type-map-coverage",
                "warning",
                "/type_maps",
                "database connector has no type_maps; native types will not be mapped to canonical Arrow types.",
                rule_doc="shared/type-maps.md",
            )
        )
    return findings


SEMANTIC_VALIDATORS: dict[str, Callable[[dict], list[dict]]] = {
    "reserved-field": check_reserved_fields,
    "expression-resolver": check_expressions,
    "transport-ref": check_transport_refs,
    "dsn-binding": check_dsn_bindings,
    "auth-shape": check_auth_shape,
    "tls-consistency": check_tls_consistency,
    "phase-resolvability": check_phase_resolvability,
    "type-map-coverage": check_type_map_coverage,
}


def is_connector_doc(doc: dict) -> bool:
    return "kind" in doc and isinstance(doc.get("transports"), dict)


def run_semantic_validators(doc: dict, only: set[str] | None = None) -> list[dict]:
    findings: list[dict] = []
    for vid, fn in SEMANTIC_VALIDATORS.items():
        if only is not None and vid not in only:
            continue
        # Skip validators that don't apply to non-connector docs
        if vid in {"transport-ref", "dsn-binding", "auth-shape", "tls-consistency", "type-map-coverage"} and not is_connector_doc(doc):
            continue
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
        except Exception as exc:
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
        findings.extend(run_semantic_validators(document))

    passed = all(f["severity"] != "error" for f in findings)
    print(json.dumps({"passed": passed, "findings": findings}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
