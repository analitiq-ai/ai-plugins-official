# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is the official directory of Analitiq Claude Code plugins for building data integration connectors and pipelines that comply with the Analitiq Data Integration Protocols (DIP). It contains two plugins, each installed independently via `.claude-plugin/plugin.json`.

## Plugins

### `analitiq-connector-builder` (v2.0.0)
Authors connector and endpoint JSON documents conforming to the published Analitiq schema contract at `schemas.analitiq.work` (dev) / `schemas.analitiq.ai` (production). Connectors may be published to the `analitiq-dip-registry` GitHub org as individual repos named `{alias}`.

**Agent chain:** `connector-builder` (skill, orchestrator) → `connector-provider-researcher` → `{api|db|storage}-connector-creator` → `endpoint-creator` (API only, parallel) → `connector-schema-validator` (loop) → `connector-drift-classifier` (optional) → write files

- `connector-builder` (skill) — orchestrator. Classifies connector kind, dispatches to the matching creator, runs the validator loop, runs drift classification, writes files. Carries shared invariant references (value expressions, lifecycle phases, connection-contract outer shape, metadata/versioning, I/O contracts) under `skills/connector-builder/references/`.
- `connector-provider-researcher` — extracts a discriminated `ProviderFacts` JSON object from official documentation. Uses `WebFetch` only — does not run web searches; the user must supply the official docs URL.
- `api-connector-creator` — authors `kind: "api"` connector bodies. Loads the `connector-spec-api` skill (auth flows, HTTP transports, pagination, replication).
- `db-connector-creator` — authors `kind: "database"` connector bodies. Loads the `connector-spec-db` skill (DSN URL templates with bindings + encoding, TLS, resource discovery, native type maps).
- `storage-connector-creator` — stub for `kind ∈ {file, s3, stdout}`. The schema accepts those kinds but the engine does not yet execute them, so this agent returns a structured refusal until support lands.
- `endpoint-creator` — authors one API endpoint JSON document per invocation. Endpoint documents have no top-level `kind` field; the parent connector's `kind` selects the endpoint schema. Database endpoints are connection-scoped and produced by the connector's `resource_discovery` workflow at runtime, not authored here.
- `connector-schema-validator` — runs Layer 1 (Draft 2020-12 JSON Schema) and Layer 2 (semantic validators: reserved-field, expression-resolver, phase-resolvability, transport-ref, dsn-binding, auth-shape, tls-consistency, type-map-coverage). Backed by `scripts/validate_connector.py`.
- `connector-drift-classifier` — diffs the assembled draft against `previous_release_path` and emits a `DriftVerdict` (patch/minor/major/none) so the orchestrator can bump `version` correctly.

### `analitiq-pipeline-builder` (v2.0.0)
Builds data integration pipelines using pre-defined connectors from the DIP registry (`analitiq-dip-registry` GitHub org). Does **not** create connectors — only downloads and wires them.

**Agent chain:** `pipeline-wizard` (skill) → `registry-browser` → `connection-creator` → `private-endpoint-creator` (DB only) → `pipeline-builder` → `stream-builder` × N (parallel)

- `pipeline-wizard` interviews the user, presents endpoints for selection, dispatches agents, collects stream results into pipeline
- `registry-browser` downloads source + destination connectors from the registry (parallel)
- `connection-creator` creates connection JSON + `.secrets/` templates for user to fill in (parallel per side)
- `private-endpoint-creator` connects to database, discovers schemas/tables, creates endpoint files in connection directory (DB connections only)
- `pipeline-builder` creates pipeline JSON shell with connections, schedule, engine, runtime defaults
- `stream-builder` builds individual stream definitions with source, destination, and field mapping (one per selected endpoint, dispatched in parallel)

## Key Concepts

- **Connector:** Reusable provider transport + auth contract. Lives in `{alias}/definition/connector.json` and validates against `https://schemas.analitiq.work/connector/latest.json`. Top-level fields: `$schema`, `kind` (one of `api`, `database`, `file`, `s3`, `stdout`), `alias`, `version`, `default_transport`, `transports`, `auth`, `connection_contract`, optional `resource_discovery` and `type_maps`. Server-managed fields (`connector_id`, `connector_schema_version`, `created_at`, `updated_at`) are stamped by the registry on insert and must NOT appear in authored documents.
- **Endpoint:** Operation template for a single resource. API endpoints live in `{alias}/definition/endpoints/{endpoint-alias}.json` and validate against `https://schemas.analitiq.work/api-endpoint/latest.json`. Database endpoints validate against `database-endpoint/latest.json` but are connection-scoped — the plugin does not author them; they are produced from the connector's `resource_discovery` workflow at runtime. Endpoint documents do not carry a `kind` field; the parent connector's `kind` selects the endpoint schema.
- **Type map:** Map from native types to Arrow canonical types. Authored as `connector.type_maps.native_to_arrow.rules` (an array of `{method, native, canonical}` entries with `method` ∈ `exact` | `regex`). For OLTP databases, the connector ships a comprehensive type map; for warehouses and document stores, restrict to documented native types. Connection-level supplements may extend coverage at runtime (e.g. PostGIS `GEOMETRY`).
- **TLS declaration:** Database transports declare TLS via `transports.<name>.tls` with `mode` (refs `connection.parameters.ssl_mode`) and `ca_certificate` (refs `secrets.ssl_ca_certificate`). The runtime materializer translates this generic declaration into driver-specific arguments. The canonical SSL mode enum is `none | require | verify-ca | verify-full | prefer`.
- **Value expression:** One of `ref` / `template` / `literal` / `function`. Refs and template variables target the closed scope list: `secrets.*`, `connection.parameters.*`, `connection.selections.*`, `connection.discovered.*`, `auth.*`, `runtime.*`, `stream.*`. Inline functions: `basic_auth`, `jwt_sign`, `url_encode`. Unknown scopes/functions are validation errors.
- **DSN bindings:** Database transports use `dsn.kind: "url_template"` with a `template` containing `{placeholder}` markers and a `bindings` map. Each binding has a `value` (value expression) and an `encoding` (closed enum: `raw`, `host`, `url_userinfo`, `url_path_segment`, `url_query_key`, `url_query_value`). Authors must NEVER pre-encode binding values; the runtime owns percent-encoding.
- **Connection:** Runtime auth credentials for a connector instance. Owned by `analitiq-pipeline-builder`, not `analitiq-connector-builder`.
- **Pipeline:** Full integration definition bundling connectors, connections, endpoints, streams, and mappings. Owned by `analitiq-pipeline-builder`.

## Versioning
Version is bumped automatically by GitHub Actions on PR merge via labels (`version:minor`, `version:patch`, `version:major`) — never bump manually.

## Connector Directory Structure (output of connector-builder)

**API connectors** (with endpoint files):
```
{alias}/
├── README.md
└── definition/
    ├── connector.json              # validates against connector/latest.json
    └── endpoints/
        └── {endpoint-alias}.json   # validates against api-endpoint/latest.json
```

**Database connectors** (no authored endpoints; `type_maps` and `tls` declared inside `connector.json`):
```
{alias}/
├── README.md
└── definition/
    └── connector.json              # validates against connector/latest.json
```

Server-managed fields (`connector_id`, `connector_schema_version`, `created_at`, `updated_at`) never appear in authored files.

## Supported Auth Types

`api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `db`, `credentials`, `aws_iam`, `none`. The set is closed by the published schema; adding another auth type requires a schema-contract change first.

## Schemas + Validation

Published schemas (dev host: `schemas.analitiq.work`; production host: `schemas.analitiq.ai`):

- Connector: `https://schemas.analitiq.work/connector/latest.json`
- API endpoint: `https://schemas.analitiq.work/api-endpoint/latest.json`
- Database endpoint: `https://schemas.analitiq.work/database-endpoint/latest.json`

Authored documents declare `$schema` with the production host (`.ai`) — that URL is locked by a `const` inside each schema. The validator currently *fetches* from the dev host (`.work`); production cutover flips fetch to `.ai`.

The `connector-schema-validator` sub-agent runs `scripts/validate_connector.py`, which performs Draft 2020-12 JSON Schema validation plus semantic validators (reserved-field, expression-resolver, phase-resolvability, transport-ref, dsn-binding, auth-shape, tls-consistency, type-map-coverage). Tests under `analitiq-connector-builder/tests/connector_validator/`.

## Canonical Types

Canonical types are Apache Arrow logical types in PascalCase (e.g. `Int32`, `Int64`, `Float64`, `String`, `Boolean`, `Binary`, `Date32`, `Time64`, `Timestamp`, `Decimal128`, `List`, `Struct`, `Map`). The vocabulary is owned by `docs/schema-contracts/shared/canonical-types.json` in `analitiq-infra`. Authoring guidance: `analitiq-connector-builder/skills/connector-spec-db/spec-type-maps.md`.

## Conventions

- JSON Schema Draft 2020-12 throughout.
- `alias` is the stable connector slug; `[a-z0-9_-]+`; immutable.
- `version` is the connector release semver, bumped per the connector release table (patch/minor/major) by `connector-drift-classifier`. First release: `1.0.0`.
- Test org_id: `d7a11991-2795-49d1-a858-c7e58ee5ecc6`.
- Agents must never author JSON that belongs to another agent's responsibility.

## PR Review Process:
After creating a PR, follow these steps.
Continue invoking the PR review process until no more errors are raised.
If raised errors are not relevant to the PR, ask if you should create GitHub issue for the rised error.

1. Use `/pr-review-toolkit` to review the PR after you have implemented all changes.
2. Wait for feedback from the review executor.
3. Determine if the raised issues are legitimate or not.
   a. if the issue is legitimate and relevant to the PR, fix it.
   b. if the issue is outside the scope of the PR, check if there is a related issue in the GitHub issue tracker. If not, create a new issue in GitHub and move on.
   c. If the issue is not a legitimate problem, summarize your thoughts on the point and move on.
4. Once you fixed all issues that need fixing, commit fixes, push to the branch.
5. Use `/pr-review-toolkit` to review again
6. Continue doing this cycle until the PR is approved by the review executor.
7. Once the PR is approved, run the tests to make sure they all pass.

