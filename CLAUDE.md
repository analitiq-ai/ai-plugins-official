# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is the official directory of Analitiq Claude Code plugins for building data integration connectors and pipelines that comply with the Analitiq Data Integration Protocols (DIP). It contains two plugins, each installed independently via `.claude-plugin/plugin.json`.

## Plugins

### `analitiq-connector-builder` (v2.0.0)
Creates new connector and endpoint definitions for the Analitiq DIP registry. Connectors are published to the `analitiq-dip-registry` GitHub org as individual repos named `{slug}`.

**Agent chain:** `wizard` (skill) → `connector-researcher` → `{type}-connector-creator` → `endpoint-creator` (API only) → manifest assembly → validate (optional)

- `wizard` interviews the user, checks for duplicates in the registry, dispatches research and creation agents, builds the manifest, updates docs, optionally validates
- `connector-researcher` researches system documentation for auth details, connection parameters, or endpoint schemas (type-agnostic — works for APIs, databases, and storage systems)
- `api-connector-creator` builds API connector definitions (connector.json, repo scaffolding) with auth flows, headers, and rate limits
- `db-connector-creator` builds database connector definitions with driver, SSH, and db auth configuration
- `storage-connector-creator` builds storage connector definitions (S3, SFTP) with credentials auth
- `endpoint-creator` builds individual endpoint JSON files under `definition/endpoints/` — **API connectors only** (database/other connectors do not have pre-defined endpoints). Creates endpoint files only; manifest and docs updates are handled by `wizard` after all endpoints complete.
- If `ANALITIQ_API_KEY` is available, `wizard` validates all JSON against `https://rest.analitiq-dev.com/v1/validate/{connector|endpoint}` and adds the `validated` topic to the repo if compliant

### `analitiq-pipeline-builder` (v2.0.0)
Builds data integration pipelines using pre-defined connectors from the DIP registry (`analitiq-dip-registry` GitHub org). Does **not** create connectors — only downloads and wires them.

**Agent chain:** `wizard` (skill) → `registry-browser` → `connection-creator` → `private-endpoint-creator` (DB only) → `pipeline-builder` → `stream-builder` × N (parallel)

- `wizard` interviews the user, presents endpoints for selection, dispatches agents, collects stream results into pipeline
- `registry-browser` downloads source + destination connectors from the registry (parallel)
- `connection-creator` creates connection JSON + `.secrets/` templates for user to fill in (parallel per side)
- `private-endpoint-creator` connects to database, discovers schemas/tables, creates endpoint files in connection directory (DB connections only)
- `pipeline-builder` creates pipeline JSON shell with connections, schedule, engine, runtime defaults
- `stream-builder` builds individual stream definitions with source, destination, and field mapping (one per selected endpoint, dispatched in parallel)

## Key Concepts

- **Connector:** Auth config + metadata for a system (API, database, S3/SFTP). Lives in `{slug}/definition/connector.json`.
- **Endpoint:** Schema definition for a single API resource. Lives in `definition/endpoints/{name}.json`. **API connectors only** — database/other connectors do not have pre-defined endpoints (their schema/table combinations are deployment-specific and discovered at runtime).
- **Manifest:** Index of all endpoints and placeholder registry for a connector. Lives in `definition/manifest.json`. The `placeholders` array registers every `${placeholder}` used in `connector.json` and endpoint files with a source category (`user_defined`, `system_defined`, `post_auth`, `protocol`, `derived`).
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
    ├── connector.json   # Auth + connector config
    ├── manifest.json    # Placeholder registry + endpoint index
    └── endpoints/       # Individual endpoint JSON files (API only)
```

**Database and other connectors** (no endpoints):
```
{slug}/
├── CLAUDE.md            # Agent reference (auth, caveats)
├── AGENTS.md            # Identical to CLAUDE.md, for non-Claude agents
├── README.md            # Human docs
├── CHANGELOG.md         # Version history
└── definition/
    ├── connector.json   # Auth + connector config
    └── manifest.json    # Connector manifest (empty endpoints array)
```

## Supported Auth Types

`api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `db`, `credentials`

## Mapping Type Enum

The system uses a strict enum: `string | integer | decimal | boolean | date | datetime | timestamp | object | array | json`. Note: `timestamp` is distinct from `datetime` — it maps to SQL `TIMESTAMP`/`DateTime` column types in database adapters. `json` is distinct from `object` — it represents a raw JSON blob/string rather than a typed structured object. Common mistakes: use `decimal` not `number`/`float`, use `integer` not `int`.

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

