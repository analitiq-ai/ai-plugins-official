# Changelog

## [3.0.0] - 2026-05-09

### Changed (BREAKING)
- Rebuilt the plugin around the published Analitiq schema contract at
  `schemas.analitiq.ai`.
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

### Fixed (PR review pass)
- `check_phase_resolvability` no longer prefixes findings with a
  spurious `/t/` segment in the JSON pointer.
- `expression-resolver` now correctly rejects unknown sub-scopes like
  `connection.bogus.x`; previously the head-one check let any
  `connection.*` ref through.
- `phase-resolvability` now also scans `${connection.discovered.X}`
  refs inside `template` strings (was ref-form only).
- `phase-resolvability` emits a warning when a `post_auth_outputs`
  entry is malformed (missing `storage`, or invalid `value_path`)
  instead of silently dropping it.
- `check_type_map_coverage` catches additional empty-ish shapes
  (`{"rules": []}`, nested `{"native_to_arrow": {"rules": []}}`).
- `fetch_schema` now writes the cache atomically (temp file + rename)
  and validates the response is parseable JSON before writing — a
  Ctrl-C mid-write can no longer poison the cache.
- Removed unused `referencing` import; `pip install jsonschema` is
  now sufficient.
- `--semantic-only` and `--json-only` are mutually exclusive (was
  silently producing `passed: true` with empty findings).
- Narrowed broad `except Exception` in schema fetch to a typed list.
- Validator agent now invokes `python3` instead of `python` for
  portability.
- Endpoint output path documented as `endpoints/{endpoint-alias}.json`
  consistently across SKILL.md, README.md, and CLAUDE.md.
- Standardized on `{alias}/` as the connector output directory name
  (was inconsistently `{slug}/` in `references/pipeline.md`).
- Narrowed the `auth-shape` validator coverage claim to OAuth2 +
  `none`; other auth types are validated by JSON Schema only.
- Reworded the "loop fixes (max 5 iterations)" wording from imperative
  to advisory; the validator script is single-shot, iteration
  discipline lives in the orchestrator.

### Tests (PR review pass)
- Test suite expanded from 3 cases to 28: at least one negative
  fixture per semantic validator, parametrized reserved-field across
  all four reserved fields, integration test that runs all 10
  reference example JSONs through the validator (catches
  schema/example drift), schema-fetch-failure test, malformed-JSON
  test, missing-path test, mutex-flag test, multi-validator
  collision test.
- Default tests run with `--semantic-only` so they don't require
  network access; one explicit `network`-marked test exercises the
  Layer 1 fetch path against the live schema.

### Round-2 PR review polish
- `_ref_phase_problem` now handles every top-level scope inline
  (runtime, auth, stream, state, connection, secrets) instead of
  delegating via fragile OR-chain at call sites. The `connection.*` /
  `secrets.*` paths are checked inside the function, not "below."
- `_runtime_phase_problem` now closed-set-validates
  `runtime.pagination.*` subkeys (only `offset` is registered).
  Removed dead double-`auth_op is None` check; collapsed to a single
  allowlist.
- The validator no longer accepts `runtime.pagination.*` at any of
  the sites it walks (transports, auth ops, post-auth ops) — those
  are connector-level, and `runtime.pagination.*` is operation-local.
  Removed the unused `in_operation` parameter from the walker; when
  endpoint operation templates are walked in a future change, the
  parameter can return.
- `check_type_map_coverage` now emits a warning when an endpoint file
  cannot be read or parsed (was: silently skipped).
- Removed dead `key2` variable in
  `_connection_or_secrets_phase_problem`.
- `check_phase_resolvability` docstring table corrected: `auth.refresh`
  is modeled at `post_auth`, not `auth`. Added an explanatory
  paragraph about why.
- `_native_from_type_format` docstring now documents the
  object/array/null exclusion explicitly.
- `spec-type-maps.md` no longer uses `params[*]` shorthand (`params`
  is an object keyed by parameter name, not an array).
- `pytest.ini` adds `addopts = --strict-markers` so a typo'd marker
  fails immediately instead of being silently treated as no marker.
- Test suite expanded from 34 → 40 offline cases. New negative
  fixtures + tests for: `runtime.oauth.code` referenced inside
  `auth.authorize` (must be flagged); `stream.*` referenced at the
  auth phase; `auth.*` referenced before post_auth;
  `runtime.pagination.*` referenced outside an operation context;
  malformed `post_auth_outputs` warnings; oneOf/anyOf/allOf and
  tuple-style `items` walking in API endpoint type-map coverage.

### Type-map coverage — API connector endpoint enforcement
- For API connectors with sibling endpoint files at
  `{alias}/definition/endpoints/`, the `type-map-coverage` validator
  now walks every endpoint document, collects `(type, format)` pairs
  from `response.schema` (recursively) and from `params[*]`, and
  emits an **error** for every uncovered native.
- Native-string convention: `format` if present, else `type`.
  Recurse into `object` / `array` / `oneOf` / `anyOf` / `allOf`.
- Database connectors keep the existing "warn on missing/empty rules"
  behavior — per-native coverage at authoring time is a runtime
  concern (discovery reconciles against the user's actual database).
- The validator now accepts an optional `doc_path` so the
  type-map-coverage check can locate the sibling `endpoints/` dir.
  Wired through from CLI; other validators ignore it.
- Documented the API native convention and example mappings in
  `skills/connector-spec-db/spec-type-maps.md`.

### Phase resolvability — full lifecycle model
- `check_phase_resolvability` now implements the full availability
  matrix from `shared/lifecycle-phases.md`. Builds an input index
  from `connection_contract.inputs` and an output index from
  `post_auth_outputs`, then walks every phase-anchored site
  (`auth.authorize/token_exchange/refresh/test`,
  `post_auth_outputs.*.{options_request,discovery_request}`,
  transports) and validates each ref / template variable against
  the matrix.
- Catches:
  - `connection.parameters.X` / `secrets.X` references to undeclared
    inputs.
  - References to inputs whose declared `phase` is later than the
    referencing template's phase (e.g. a `phase: post_auth` input
    referenced in `auth.authorize`).
  - `connection.selections.*` / `connection.discovered.*` references
    to keys no `post_auth_output` produces.
  - `runtime.*` keys outside the closed set
    (`run_id`, `current_time`, `batch_size`, `pagination.*`,
    `oauth.{code,state,redirect_uri,pkce_verifier}`).
  - `runtime.oauth.*` referenced when `auth.type` is not
    `oauth2_authorization_code`.
  - `runtime.oauth.code` referenced outside `auth.token_exchange`.
  - `runtime.oauth.*` referenced inside `auth.refresh`.
  - `runtime.pagination.*` referenced outside an operation context.
- `auth.refresh` is modeled with `post_auth`-equivalent scope
  availability (it runs after the in-flight authorization-code
  workflow, so persisted `auth.refresh_token` is accessible) while
  keeping the spec's `runtime.oauth.*` exclusion.
- 5 new negative fixtures + tests covering: unknown runtime key,
  oauth-runtime on non-OAuth connector, runtime.oauth.code in
  refresh, undeclared connection.parameters input, post-auth input
  referenced in auth.authorize.

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
