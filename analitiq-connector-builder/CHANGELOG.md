# Changelog

## Unreleased

### Changed (BREAKING)
- Rebuilt the plugin around the published Analitiq schema contract at
  `schemas.analitiq.work` (dev) / `schemas.analitiq.ai` (production).
  The plugin now produces connector and endpoint JSON documents that
  validate directly against the published JSON Schemas — no more
  bespoke `placeholders` / `endpoints` arrays, no separate
  `type-map.json` / `ssl-mode-map.json` files. Type maps and TLS live
  inside `connector.json`.
- New orchestrator skill `connector-builder` (replaces `connector-wizard`).
- New sub-agents: `connector-provider-researcher` (replaces
  `connector-researcher`; now WebFetch-only, no WebSearch),
  `connector-schema-validator` (Layer 1 JSON Schema + Layer 2 semantic
  validators), `connector-drift-classifier` (patch/minor/major bump
  classification).
- Rewritten creator agents `api-connector-creator` and
  `db-connector-creator` to load the dedicated `connector-spec-api` and
  `connector-spec-db` skills and emit the new schema-aligned shapes
  (DSN url-template bindings with closed encoding enum, generic TLS
  declarations, post-auth outputs with `mode ∈ {user_selection, auto_discovery}`).
- `endpoint-creator` no longer writes a top-level `kind` field on
  endpoint documents — the parent connector's `kind` selects the
  endpoint schema.
- New `scripts/validate_connector.py` Python validator with pytest
  fixtures under `tests/connector_validator/`.

### Removed
- `connector-wizard`, `connector-assembly`, `connector-scaffolding`,
  `endpoint-spec`, `registry-submission`, `type-mapping-spec` skills.
- `connector-researcher`, `registry-contributor`,
  `storage-connector-creator` (real impl) agents.
- `placeholders` and `endpoints` arrays from authored `connector.json`.
- Standalone `type-map.json` and `ssl-mode-map.json` files (folded into
  `connector.json`).

### Added
- `storage-connector-creator` stub agent for `kind ∈ {file, s3, stdout}`
  — schema accepts these kinds but the engine doesn't yet execute them.
- Six API reference examples (api_key, api-key dynamic host, basic_auth,
  OAuth2 authorization-code with multi-origin transports + post-auth
  discovery, OAuth2 client-credentials, JWT) and four DB reference
  examples (PostgreSQL, MySQL, Snowflake, MongoDB) — all validate clean
  against the published schema.
- Pre-flight collision check in the orchestrator (phase 0): if a
  directory matching `{alias}/` already exists, the build halts and
  asks the user to remove it manually. Acts as a stopgap against
  overwriting legacy-shape connectors until a real migration tool is
  built.

## [2.0.0] - 2026-03-28

### Added
- Connector builder orchestrator (`connector-wizard`) with duplicate checking and validation
- Connector researcher agent for API, database, and storage systems
- Type-specific connector creators (API, database, storage)
- Endpoint creator agent for API connectors
- Connector scaffolding skill with shared templates
- Type-specific connector spec skills (API, database, storage)
- Endpoint specification skill
- Research briefs for structured agent dispatch
- Optional validation against Analitiq API
- `effort` and `maxTurns` guardrails on all agents
- `disable-model-invocation` on reference-only skills
- Supporting file navigation in skill SKILL.md files
