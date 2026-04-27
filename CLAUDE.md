# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is the official directory of Analitiq Claude Code plugins for building data integration connectors and pipelines that comply with the Analitiq Data Integration Protocols (DIP). It contains two plugins, each installed independently via `.claude-plugin/plugin.json`.

## Plugins

### `analitiq-connector-builder` (v2.0.0)
Creates new connector and endpoint definitions for the Analitiq DIP registry. Connectors are published to the `analitiq-dip-registry` GitHub org as individual repos named `{slug}`.

**Agent chain:** `connector-wizard` (skill) → `connector-researcher` → `{type}-connector-creator` → `endpoint-creator` (API only) → connector assembly → validate (optional) → `registry-contributor` (optional)

- `connector-wizard` interviews the user, checks for duplicates in the registry, dispatches research and creation agents, finalizes `connector.json` (placeholder registry + endpoint index), updates docs, optionally validates, and optionally contributes to the community registry
- `connector-researcher` researches system documentation for auth details, connection parameters, or endpoint schemas (type-agnostic — works for APIs, databases, and storage systems)
- `api-connector-creator` builds API connector definitions (connector.json, repo scaffolding) with auth flows, headers, and rate limits
- `db-connector-creator` builds database connector definitions with driver, SSH, and db auth configuration
- `storage-connector-creator` builds storage connector definitions (S3, SFTP) with credentials auth
- `endpoint-creator` builds individual endpoint JSON files under `definition/endpoints/` — **API connectors only** (database/other connectors do not have pre-defined endpoints). Creates endpoint files only; the placeholder registry, endpoint index, and docs updates are handled by `connector-wizard` after all endpoints complete.
- If `ANALITIQ_API_KEY` is available, `connector-wizard` validates all JSON against `https://api.analitiq-dev.com/v1/validate/{connector|endpoint}` and records validation status
- `registry-contributor` (optional) scans for PII/credentials, creates a sanitized copy if needed, pushes to the user's GitHub account, and opens a submission issue in `analitiq-dip-registry/connector-submissions`

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

- **Connector:** Auth config + metadata + placeholder registry + endpoint index for a system (API, database, S3/SFTP). Lives in `{slug}/definition/connector.json`. Carries `version`, `placeholders`, and `endpoints` fields directly — there is no separate `manifest.json`. The `placeholders` array registers every `${placeholder}` used in the auth body and endpoint files with a source category (`user_defined`, `system_defined`, `post_auth`, `protocol`, `derived`).
- **Endpoint:** Schema definition for a single API resource. Lives in `definition/endpoints/{name}.json`. **API connectors only** — database/other connectors do not have pre-defined endpoints (their schema/table combinations are deployment-specific and discovered at runtime).
- **Type map:** Ordered list of rules mapping a connector's native types to canonical Arrow logical types. Lives in `definition/type-map.json`. Required on every connector. Format spec: `analitiq-connector-builder/docs/type-map-format.md`.
- **SSL mode map:** Maps native driver SSL mode values to the canonical enum (`none | require | verify-ca | verify-full | prefer`). Lives in `definition/ssl-mode-map.json`. SSL-capable databases only — omitted entirely otherwise.
- **Connection:** Runtime auth credentials for a connector instance. Secrets go to `.secrets/{connection_id}.json`.
- **Pipeline:** Full integration definition bundling connectors, connections, endpoints, streams, and mappings.

## Versioning
Version is bumped automatically by GitHub Actions on PR merge via labels (`version:minor`, `version:patch`, `version:major`) — never bump manually.

## Connector Directory Structure (output of connector-builder)

**API connectors** (with endpoints):
```
{slug}/
├── CLAUDE.md            # Agent reference (auth, endpoints, caveats)
├── AGENTS.md            # Identical to CLAUDE.md, for non-Claude agents
├── README.md            # Human docs
├── CHANGELOG.md         # Version history
└── definition/
    ├── connector.json   # Auth + placeholder registry + endpoint index
    ├── type-map.json    # Native → Arrow canonical type mapping (required)
    └── endpoints/       # Individual endpoint JSON files (API only)
```

**Database connectors** (no endpoints; `ssl-mode-map.json` only on SSL-capable drivers):
```
{slug}/
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── CHANGELOG.md
└── definition/
    ├── connector.json    # Auth + driver + SSH config (placeholders/endpoints arrays empty)
    ├── type-map.json     # Native → Arrow canonical type mapping (required)
    └── ssl-mode-map.json # Native SSL mode → canonical enum (only if driver supports TLS)
```

**Storage connectors** (no endpoints, no SSL map):
```
{slug}/
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── CHANGELOG.md
└── definition/
    ├── connector.json   # Auth + credentials config (placeholders/endpoints arrays empty)
    └── type-map.json    # Connector-level metadata types only (file-data typing is engine-side)
```

## Supported Auth Types

`api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `db`, `credentials`

## Canonical Types

Canonical types are Apache Arrow logical types. The machine-readable vocabulary lives in `analitiq-connector-builder/schemas/canonical-types.json` (`$id: https://api.analitiq-dev.com/schemas/canonical-types.json`) — do not restate the vocabulary in prose. Each connector ships a `definition/type-map.json` that maps its native types to canonical ones. Authoring guidance: `analitiq-connector-builder/skills/type-mapping-spec/SKILL.md`. Format spec: `analitiq-connector-builder/docs/type-map-format.md`.

**Layout convention.** Both plugins use a `definition/` directory that holds `type-map.json` alongside an `endpoints/` subdirectory — fully symmetric:

- Connector side: `{slug}/definition/type-map.json` and `{slug}/definition/endpoints/*.json`.
- Pipeline side: `connections/{alias}/definition/type-map.json` and `connections/{alias}/definition/endpoints/{schema}-{table}.json`.

The pipeline-side `type-map.json` is an **optional supplement** — used when pipeline-builder discovers private-endpoint natives (e.g., PostGIS `GEOMETRY`, pgvector `vector`) that the base connector's `type-map.json` doesn't cover. Engine resolution order: connection-level supplement → connector-level base → hard error on no match. Pipeline-builder implementation of this layout is tracked separately; the convention is recorded here so both sides follow it.

## Conventions

- UUIDs are used for all IDs (`connector_id`, `endpoint_id`, `connection_id`, `pipeline_id`, `stream_id`)
- Stream and pipeline IDs include a version suffix: `{uuid}_v1`
- JSON Schema draft 2020-12 is used for endpoint schemas
- Connection refs: `conn_1` = source, `conn_2` = first destination, `conn_3` = second, etc.
- OAuth connections: `connection_type: "oauth2"` and `host` must be null
- Test org_id: `d7a11991-2795-49d1-a858-c7e58ee5ecc6`
- Agents must never create JSON that belongs to another agent's responsibility

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

