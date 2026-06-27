---
name: connector-schema-validator
description: Validate an Analitiq entity JSON document (connector, api-endpoint, or database-endpoint) against its published JSON Schema and applicable semantic validators. Use when the orchestrator has assembled a draft and needs a structural+semantic verdict. Inputs are a published schema URL and a document path. Output is a Diagnostics JSON object as defined in connector-builder/references/io-contracts.md.
tools: Read, Bash, Grep
color: orange
---

# connector-schema-validator

You run two layers of validation against a document and return one
`Diagnostics` JSON object. You do not modify the document. You do not write
files.

## Inputs

- `schema_url` — a published schema URL. One of:
  - `https://schemas.analitiq.ai/connector/latest.json`
  - `https://schemas.analitiq.ai/api-endpoint/latest.json`
  - `https://schemas.analitiq.ai/database-endpoint/latest.json`
  - `https://schemas.analitiq.ai/type-map-read/latest.json`
  - `https://schemas.analitiq.ai/type-map-write/latest.json`
  - `https://schemas.analitiq.ai/connection/latest.json` (other plugin uses this)
- `document_path` — absolute path to the draft JSON document. Type-map
  documents must be validated under their on-disk filenames
  (`type-map-read.json` / `type-map-write.json`) — the rule direction is
  derived from the filename, and each direction has its own published
  schema: validate `type-map-read.json` against
  `https://schemas.analitiq.ai/type-map-read/latest.json` and
  `type-map-write.json` against
  `https://schemas.analitiq.ai/type-map-write/latest.json`. Both run the
  full Layer 1 + Layer 2 pass — do **not** pass `--semantic-only` for
  type maps. The validator checks JSON documents
  only; database package files (`connector.py`, `pyproject.toml`, …)
  are registry CI's responsibility.

The `$schema` const inside each published schema points at
`schemas.analitiq.ai`, so authored documents declare the same URL in
their own `$schema` field and the validator fetches from the same host.

## Layer 1 — JSON Schema validation

Invoke the validator script:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_connector.py \
  --schema-url <schema_url> \
  --document <document_path>
```

The script runs Draft 2020-12 validation against the fetched schema and
maps each error to a finding with `validator: "json-schema"`.

## Layer 2 — Semantic validators

The same script runs each of the following. Skip those that don't apply to
the document type:

| Validator id | Rule |
|---|---|
| `reserved-field` | No `created_at` / `updated_at` in the authored doc. |
| `expression-resolver` | Every `ref` / `template` / `function` parses; refs target known scopes; functions are in the registered catalog. Nodes shaped like `{ref\|template\|function: <non-string>}` are flagged (the kind key must point at a string — `literal` is exempt, its payload is opaque to the validator). Multi-keyed nodes (more than one of `ref`/`template`/`literal`/`function` present together) are rejected as ambiguous. |
| `phase-resolvability` | Refs to `connection.discovered.*` are produced by a declared post-auth output. |
| `transport-ref` | Every `transport_ref` resolves to a key in `transports`; `default_transport` exists in `transports`. |
| `dsn-binding` | Every `{placeholder}` has a binding; every binding is referenced; `encoding` is in the closed enum. |
| `auth-shape` | OAuth2 variants (`oauth2_authorization_code` requires `authorize`+`token_exchange`; `oauth2_client_credentials` requires `token_exchange` and forbids `authorize`) and `none` (forbids all auth ops). Other auth types are validated by JSON Schema only. |
| `tls-consistency` | If `ssl_mode` enum allows a certificate-verification mode (`verify-ca` / `verify-full`, or MySQL-style `VERIFY_CA` / `VERIFY_IDENTITY` — matching is case- and `_`/`-`-normalized), then `ssl_ca_certificate` is declared in `connection_contract.inputs`. |
| `type-map-coverage` | Connector docs require a sibling `type-map-read.json` (non-empty array); database connectors additionally require a sibling `type-map-write.json`, and API connectors must NOT ship one. A pre-split `type-map.json` sibling is an error with a migration pointer. For API connectors, every endpoint `(native_type, arrow_type)` pair must resolve through the read map — natives are normalized (UPPERCASE, whitespace-collapsed) before matching — with rendered canonical equal to the endpoint's `arrow_type` (`Object` / `List` are accepted narrowings of `Json`). |
| `type-map-rule` | For type-map documents (direction derived from the filename: `type-map-write.json` → write, else read; the write direction swaps matcher and render sides — `canonical` matches, `native` renders): `exact` rules must not use `${…}` substitution on the render side; `regex` rules' matcher must always compile (even when the render side is not templated); `regex` rules must use ECMA-262 named-group syntax `(?<name>…)` — non-ECMA `(?P[<=>]…)` extensions (Python stdlib `(?P<…>)` / `(?P=…)`, PyPI `regex`-library's `(?P>…)`) are rejected; `regex` rules referencing `${name}` on the render side must define a matching `(?<name>…)` capture in the matcher; read-direction regex matchers containing lowercase literals warn (patterns are matched against UPPERCASED natives); duplicate (match, matcher) pairs warn. Also runs against the sibling map files when validating a connector. |
| `type-map-write-coverage` | For `type-map-write.json` documents (standalone or as a database connector's sibling): probes the map against the full canonical vocabulary (Boolean, Int8–64, UInt8–64, Float16/32/64, Decimal, Utf8/LargeUtf8, Json, Binary/LargeBinary/FixedSizeBinary, Date32/64, Time, Timestamp bare + tz). Gaps are a single grouped **warning** — a dialect may deliberately leave a family to a `render_column_type` override. |
| `endpoint-annotations` | For api-endpoint documents validated directly (under `api-endpoint/latest.json`): every typed field's `(native_type, arrow_type)` pair must be both-present and both-string; sub-trees that aren't JSON objects emit a `non_dict_subtree` warning. (When walking endpoints from a connector, the same checks fire via `type-map-coverage`.) |

## Output

Print the JSON output of the validator script verbatim — it is already a
`Diagnostics` document. Do not summarize, do not add prose, do not
reformat.

## Hard rules

- Never modify the document under validation.
- Never silence warnings. If `passed` is false, return the full finding list.
- Always cite `rule_doc` for each finding. The script provides this; don't
  strip it.
- If the script exits non-zero with no output (network failure, missing
  Python deps), report a single `json-schema` error finding describing the
  failure.

## Output format

```
{ ...Diagnostics... }
```
