# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is the official directory of Analitiq Claude Code plugins for building data integration connectors and pipelines that comply with the Analitiq Data Integration Protocols (DIP). It contains two plugins, each installed independently via `.claude-plugin/plugin.json`.

## Plugins

### `analitiq-plugin-connector-builder` (v1.2.0)
Creates new connector and endpoint definitions for the Analitiq DIP registry. Connectors are published to the `analitiq-dip-registry` GitHub org as individual repos named `connector-{slug}`.

**Agent chain:** `start` (skill) → `connector-creator` → `endpoint-creator`, with `api-researcher` invoked automatically for API-type connectors.

- `start` interviews the user, checks for duplicates in the registry, then dispatches agents
- `connector-creator` builds `connector.json`, `manifest.json`, and repo scaffolding (CLAUDE.md, AGENTS.md, README.md, CHANGELOG.md)
- `endpoint-creator` builds individual endpoint JSON files under `definition/endpoints/` and updates the manifest
- `api-researcher` fetches auth details and endpoint schemas from official API docs (WebFetch → WebSearch → Playwright fallback)

### `analitiq-plugin-dataflow` (v2.0.0)
Builds data integration pipelines using pre-defined connectors from the DIP registry (`analitiq-dip-registry` GitHub org). Does **not** create connectors — only downloads and wires them.

**Agent chain (strictly sequential with gates):**
1. `registry-browser` — downloads source + destination connectors (parallel)
2. `connection-creator` — collects credentials, produces connection JSON + `.secrets/` files (parallel per side)
3. `endpoint-data-mapper` — creates field-level mappings with three-way consistency (assignments, source_to_generic, generic_to_destination)
4. `pipeline-assembler` — assembles the final pipeline JSON with all components

## Key Concepts

- **Connector:** Auth config + metadata for a system (API, database, S3/SFTP). Lives in `connector-{slug}/definition/connector.json`.
- **Endpoint:** Schema definition for a single API resource or DB table. Lives in `definition/endpoints/{name}.json`.
- **Manifest:** Index of all endpoints for a connector. Lives in `definition/manifest.json`. Version is bumped automatically by GitHub Actions on PR merge via labels (`version:minor`, `version:patch`, `version:major`) — never bump manually.
- **Connection:** Runtime auth credentials for a connector instance. Secrets go to `.secrets/{connection_id}.json`.
- **Pipeline:** Full integration definition bundling connectors, connections, endpoints, streams, and mappings.

## Connector Directory Structure (output of connector-builder)

```
connector-{slug}/
├── CLAUDE.md            # Agent reference (auth, endpoints, caveats)
├── AGENTS.md            # Identical to CLAUDE.md, for non-Claude agents
├── README.md            # Human docs
├── CHANGELOG.md         # Version history
└── definition/
    ├── connector.json   # Auth + connector config
    ├── manifest.json    # Endpoint index
    └── endpoints/       # Individual endpoint JSON files
```

## Supported Auth Types

`api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `db`, `credentials`

## Mapping Type Enum

The system uses a strict enum: `string | integer | decimal | boolean | date | datetime | object | array`. Common mistakes: use `decimal` not `number`/`float`, use `integer` not `int`, use `datetime` not `timestamp`.

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

