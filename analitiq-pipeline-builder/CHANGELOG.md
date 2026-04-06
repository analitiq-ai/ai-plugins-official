# Changelog

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
