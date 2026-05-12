# Analitiq Connector Builder Plugin

Claude Code plugin that authors connector JSON documents conforming to the
published Analitiq schema contract at
[`schemas.analitiq.ai`](https://schemas.analitiq.ai). Supports API and database
connectors; storage kinds (`file`, `s3`, `stdout`) are accepted by the schema
but the engine doesn't yet execute them — those are stubbed.

## What it does

Given a provider name and an official documentation URL, the plugin:

1. Researches the provider's auth model, transports, and endpoints.
2. Classifies kind, auth type, and transport types.
3. Dispatches a kind-specific creator agent that authors the connector body.
4. Authors endpoint files alongside (API connectors only — DB endpoints are
   discovered at runtime).
5. Validates everything against the published JSON schemas plus a layer of
   semantic validators (DSN bindings, auth shape, TLS consistency, etc.).
6. Classifies version drift against the previous release and bumps `version`
   accordingly.
7. Writes the connector and endpoint files to disk at predictable paths.

**Usage:** Launch Claude Code and say *"build a connector for &lt;provider&gt;"*
or *"/connector-builder &lt;provider&gt;"*.

## Architecture

```
connector-builder (skill, orchestrator)
├── connector-provider-researcher   # extracts ProviderFacts from official docs (no WebSearch)
├── api-connector-creator           # authors kind=api connectors (loads connector-spec-api)
├── db-connector-creator            # authors kind=database connectors (loads connector-spec-db)
├── endpoint-creator                # authors API endpoint documents
├── storage-connector-creator       # stub for kind ∈ {file, s3, stdout}
├── connector-schema-validator      # JSON Schema + semantic validation
└── connector-drift-classifier      # patch/minor/major bump from diff
```

The orchestrator owns classification and cross-cutting steps. Each creator
agent owns the authoring vocabulary for its kind via a dedicated spec skill
(`connector-spec-api`, `connector-spec-db`, `connector-spec-storage`).

## Supported kinds

| Kind | Status | Auth types | Examples |
|---|---|---|---|
| `api` | shipped | `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `credentials`, `aws_iam`, `none` | Stripe, Pipedrive, Wise, Xero |
| `database` | shipped | `db` | PostgreSQL, MySQL, Snowflake, MongoDB |
| `file` / `s3` / `stdout` | stubbed | n/a | Recognized by schema; engine support pending. |

## Validation

The plugin includes a Python validator script
(`scripts/validate_connector.py`) that runs:

1. **JSON Schema validation** (Draft 2020-12) against the published schema:
   - Connector → `https://schemas.analitiq.ai/connector/latest.json`
   - API endpoint → `https://schemas.analitiq.ai/api-endpoint/latest.json`
   - Database endpoint → `https://schemas.analitiq.ai/database-endpoint/latest.json`
2. **Semantic validators** for rules JSON Schema can't express:
   - `reserved-field`, `expression-resolver`, `phase-resolvability`,
     `transport-ref`, `dsn-binding`, `auth-shape`, `tls-consistency`,
     `type-map-coverage`.

Run directly:

```bash
python scripts/validate_connector.py \
  --schema-url https://schemas.analitiq.ai/connector/latest.json \
  --document path/to/connector.json
```

Output is a single `Diagnostics` JSON object. Exit 0 iff `passed: true`.

Tests live under `tests/connector_validator/`. Run with `pytest`.

## Schema host

- The validator fetches schemas from `https://schemas.analitiq.ai`.
- Authored documents declare `$schema` with the same host — the URL is
  locked by a `const` inside the published schema.

## File output

For each successfully built connector:

```
{alias}/
├── definition/
│   ├── connector.json              # the connector body
│   └── endpoints/                  # api connectors only
│       └── {endpoint-alias}.json
└── README.md
```

Server-managed fields (`connector_id`, `connector_schema_version`,
`created_at`, `updated_at`) are NEVER written to disk — the registry
stamps them on insert/update.

### Existing directories are not overwritten

If a directory matching the connector's `{alias}` already exists in
the current working directory, the orchestrator halts and asks the
user to remove it manually before re-running. The plugin does not
migrate legacy-shape connectors — pre-existing files (with
`placeholders` arrays, separate `manifest.json` / `type-map.json` /
`ssl-mode-map.json`) must be deleted first so the rebuild can produce
a clean schema-aligned connector from scratch. The orchestrator never
deletes files on the user's behalf.

## Installation

```bash
claude plugin add ./analitiq-connector-builder
```

## Links

- [Analitiq DIP Registry](https://github.com/analitiq-ai/analitiq-dip-registry) — community connector submissions.
- [Schema contracts](https://github.com/analitiq-ai/analitiq-infra/tree/main/docs/schema-contracts) — authoritative shape specs.
- [Published schemas](https://schemas.analitiq.ai) — the JSON Schemas the validator runs against.

## License

Apache 2.0 — see [LICENSE](LICENSE).
