# Changelog

## Unreleased

### Changed
- Merged `manifest.json` into `connector.json`. The `version`, `placeholders`, `endpoints`, and
  optional root `deprecated` fields now live directly inside `connector.json`; the separate
  `manifest.json` file is no longer produced. Renamed the `manifest-assembly` skill to
  `connector-assembly` to reflect the new flow.

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
