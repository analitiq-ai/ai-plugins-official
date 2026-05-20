# Changelog

## [unreleased]

### Changed
- **Identity migration: `alias` → `{object}_id`.** Aligns the plugin
  with the published Analitiq schema contracts at `schemas.analitiq.ai`,
  which now enforce typed identity fields:
  - `pipeline.pipeline_id`, `stream.stream_id`,
    `connection.connection_id` are **RFC-4122 UUIDs**. The plugin
    generates a fresh UUID per document at authoring time and threads
    it through cross-references; the registry assigns one on ingest if
    omitted.
  - `connection.connector_id` is a **slug** (or UUID — schema does not
    constrain). Authored as the connector slug downloaded from the
    DIP registry.
  - `database_endpoint.endpoint_id` is a **slug**
    (`^[a-z0-9][a-z0-9_-]*$`), authored verbatim from
    `<schema>_<name>`.
  - `endpoint_ref` inner field renamed `alias` → `endpoint_id`.
  - Cross-references (`pipeline.connections.source`,
    `pipeline.connections.destinations[]`, `pipeline.streams[]`,
    `stream.pipeline_id`, `endpoint_ref.connection_id`) carry the
    referenced document's UUID identity.
  - Directory layout stays slug-based and human-readable
    (`pipelines/<pipeline-slug>/`, `connections/<connection-slug>/`,
    `connections/<connection-slug>/endpoints/<endpoint-slug>.json`,
    `pipelines/<pipeline-slug>/streams/<stream-slug>.json`). The slug
    is independent of the UUID identity stored inside the document.

- **Connection envelope: `parameters` + `secret_refs` → single
  `values`.** The closed `connection/latest.json` schema accepts only
  `$schema`, `connection_id`, `connector_id`, `display_name`,
  `description`, `values`, and `tags` (with `connector_id` the only
  required field). The plugin now writes a single flat `values`
  envelope keyed by connection-contract input name. For inputs whose
  connector contract bucket is `secrets`, the plugin writes a
  human-readable placeholder (`"<see .secrets/credentials.json>"`)
  into `values` and emits a `.secrets/credentials.json` template the
  user fills in. The user (or CI) merges secret values from
  `.secrets/` into `values` before submitting the connection to the
  registry. The server routes `values` entries into the persisted
  parameters / selections / secrets buckets per the connector
  contract.

- **Closed-schema sweep.** Every published schema now declares
  `additionalProperties: false`. Authored documents emit only fields
  in the published `properties` list — no `x-*` extensions, no legacy
  fields. `references/extension-policy.md` rewritten to reflect
  closed-schema behavior.

### Validator
- Renamed `endpoint_ref.alias` → `endpoint_ref.endpoint_id` in the
  destination-uniqueness key.
- Removed the `secret-ref-format` Layer 2 validator (the closed
  connection schema rejects `secret_refs` entirely; the `.secrets/`
  template is a local-only file).
- `pipeline-stream-consistency` and `status-lifecycle` derive the
  pipeline's directory slug from the document path (used only to scope
  stream-file discovery) and compare stream `pipeline_id` against the
  authored `pipeline.pipeline_id` UUID for cross-document matching.
- `reserved-field` validator lists no longer reserve
  `pipeline_id` / `stream_id` / `connection_id` / `endpoint_id` /
  `connector_id` — those are authored fields under the new contract.

### Fixtures + examples
- All `valid_*.json` and `invalid_*.json` validator fixtures and all
  `skills/*/examples/*.example.json` reference examples rewritten to
  the new identity + envelope contract.

### Migration
- Pipelines, connections, and endpoint files from prior plugin
  releases are not migrated and must be regenerated. The validator's
  closed-schema enforcement will reject the legacy shape with a clear
  `additionalProperties` finding.

## [4.0.0] - 2026-05-11

Realignment with the published Analitiq schema contract. Breaking change: the
plugin no longer emits the legacy `conn_1`/`conn_2` positional connection refs
or the legacy server-managed mapping fields (`source_to_generic`,
`generic_to_destination`, `assignments_hash`, `type_mapping_assignments_hash`).
The authored mapping block keeps `assignments` only; the registry computes the
rest. Pre-existing pipelines, connections, and endpoint files from 3.x are not
migrated and must be regenerated from scratch.

### Added
- `scripts/validate_pipeline.py` — Draft 2020-12 JSON Schema validation plus
  semantic validators (`reserved-field`, `versioned-id-format`,
  `schedule-shape`, `runtime-ranges`, `endpoint-ref-shape`, `mapping-shape`,
  `filter-operators`, `secret-ref-format`, `column-uniqueness`,
  `pipeline-stream-consistency`, `status-lifecycle`). Selects schema by
  `--entity {pipeline|stream|connection|database_endpoint}`.
- `tests/pipeline_validator/` — pytest suite with passing + failing fixtures
  per validator, reference-example sweep, and a `network`-marked Layer-1 live
  test.
- `agents/pipeline-provider-researcher.md` — collects `PipelineFacts` from the
  user (source/destination connector aliases, replication, write mode,
  schedule, naming). WebFetch only; no WebSearch.
- `agents/pipeline-schema-validator.md` — wraps `validate_pipeline.py` and
  surfaces findings to the orchestrator's fix-and-revalidate loop.
- `agents/pipeline-drift-classifier.md` — surfaces structural diff against a
  previous release path.
- `skills/pipeline-builder/` — orchestrator skill with `references/`
  (`pipeline.md`, `enum-mappers.md`, `io-contracts.md`,
  `identity-and-versioning.md`, `reserved-fields.md`, `extension-policy.md`,
  `schema-hosts.md`).
- `skills/pipeline-spec/`, `skills/stream-spec/`, `skills/connection-spec/`,
  `skills/endpoint-spec/` — spec skills with `disable-model-invocation: true`
  and `examples/` per entity that validate clean against the published
  schemas.
- `pytest.ini` — declares the `network` marker.

### Changed
- `.claude-plugin/plugin.json` — bumped to `4.0.0`; description rewritten.
- `README.md` — declares the four published schema URLs the plugin authors
  against, the new agent chain, and the new file layout.
- `agents/registry-browser.md` — validates downloaded `connector.json` against
  `connector/latest.json` (delegating to the shared validator script).
- `agents/connection-creator.md` — emits `connection/latest.json` shape with
  `secret_refs` and templated `.secrets/` paths.
- `agents/private-endpoint-creator.md` — emits `database-endpoint/latest.json`
  shape: `database_object{catalog, schema, name, object_type}` plus typed
  `columns[]` (with `native_type`, optional `arrow_type` PascalCase) and
  optional `primary_keys[]`.
- `agents/pipeline-creator.md` (renamed from `pipeline-builder.md`) — emits
  `pipeline/latest.json` shape with versioned connection IDs (placeholder
  UUIDs minted by the orchestrator).
- `agents/stream-creator.md` (renamed from `stream-builder.md`) — emits
  `stream/latest.json` shape: `endpoint_ref{scope, connection_id, alias}`,
  source filters / replication / pagination, destination write modes, and
  the assignments-only mapping (server owns the rest).

### Removed
- `skills/pipeline-wizard/` — replaced by the new `skills/pipeline-builder/`
  orchestrator skill.
- `skills/mapping-spec/` — folded into `stream-spec/spec-mapping.md`. The
  `source_to_generic`, `generic_to_destination`, `assignments_hash`, and
  `type_mapping_assignments_hash` fields are server-managed under the new
  schema and the plugin no longer emits them.
- Positional connection references (`conn_1`, `conn_2`, …). Replaced by
  versioned UUID placeholders.
- `pipelines/manifest.json` output. Not part of any published schema.

## [3.0.0] - 2026-03-30

### Added
- Pipeline builder agent — creates pipeline JSON shell with connection refs and defaults
- Stream builder agent — builds individual streams with field mapping (parallel dispatch)
- Private endpoint creator agent — discovers schemas/tables from live DB connections
- Stream specification skill based on StreamPayload Pydantic model
- Endpoint specification skill for private DB endpoints (DbConnectorEndpointRecord)

### Changed
- Restructured agent chain: pipeline-wizard → registry-browser → connection-creator → private-endpoint-creator → pipeline-builder → stream-builder × N
- Connection creator simplified — uses .secrets templates instead of HTML credential forms
- Pipeline spec aligned with PipelineConfig Pydantic model
- Pipeline-wizard now interviews for endpoint selection after connections are created

### Removed
- Endpoint data mapper agent (replaced by stream-builder)
- Pipeline assembler agent (replaced by pipeline-builder + pipeline-wizard assembly)
- HTML credential form generation from connection-spec

## [2.0.0] - 2026-03-28

### Added
- Pipeline orchestrator (`pipeline-wizard`) with phased agent dispatch
- Registry browser agent for downloading connectors from the DIP registry
- Connection creator agent with support for 7 auth types
- Endpoint data mapper agent with three-way sync validation
- Pipeline assembler agent with cross-reference validation
- Connection, mapping, and pipeline specification skills with examples
- `effort` and `maxTurns` guardrails on all agents
- `disable-model-invocation` on reference-only skills
- Supporting file navigation in skill SKILL.md files
