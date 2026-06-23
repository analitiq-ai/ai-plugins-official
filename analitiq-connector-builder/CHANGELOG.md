# Changelog

## [unreleased]

### Added
- **Definition-of-Done self-check for the connector creators.** New
  `connector-builder/references/definition-of-done.md` carries a shared-core
  checklist, and `api-connector-creator` / `db-connector-creator` each gained
  a kind-specific `## Definition of Done` section run as a gate before
  returning `CreatorOutput`. The lists deliberately cover what the
  `connector-schema-validator` cannot enforce — classification correctness,
  read-map completeness against the provider's docs, the both-directions
  principle, driver-selection discipline (async-only SQLAlchemy, decision
  order), and the non-JSON artifacts the in-plugin validator never sees
  (package files, README) — so they add no duplicated source of truth with
  the validator, save one deliberately-labeled API/DB boundary check.

### Fixed
- **Upsert API endpoints now document the required `conflict_keys`.**
  `agents/endpoint-creator.md` step 4 and the `connector-spec-api` SKILL
  operations cross-reference omitted `conflict_keys`, which the published
  `api-endpoint` schema **requires on the `upsert` write mode** (an array
  of ≥1 top-level `input.schema` field names forming the natural key the
  upsert matches on) and **forbids on `insert`**. Without that guidance the
  authoring agent would emit an `upsert` missing `conflict_keys` (a Layer 1
  failure that churns the validate→fix loop) or silently fall back to
  `insert`, dropping upsert capability. Docs-only fix; the schema and
  validator were already correct. Surfaced in #46.
- **Validator now catches empty placeholders instead of ignoring them.**
  Every placeholder-extraction regex used `[^}]+` (one-or-more), so an empty
  placeholder matched nothing and slipped through silently — at runtime it
  resolves to nothing, corrupting the URL/header (value-expression `${}`), the
  connection string (DSN `{}`), or surviving as a literal in rendered DDL
  (type-map `${}`). Widened all of them to `[^}]*` and added explicit errors:
  `expression-resolver` flags an empty/whitespace template variable,
  `type-map-rule` flags an empty render-side placeholder, and `dsn-binding`
  flags an empty `{}` in a `url_template`. All four sites are covered —
  `check_expressions`, `check_phase_resolvability`, `_PLACEHOLDER_RE`
  (type maps), and `check_dsn_bindings`. Fixes #48.

### Changed
- **Type-map split: `type-map.json` → `type-map-read.json` + `type-map-write.json`**
  (per `connector-driver-selection.md` / `dip-registry-connector-packages.md`
  specs; the engine reads only the new filenames).
  - The read map (`type-map-read.json`, native → Arrow) is required for
    every connector; the new write map (`type-map-write.json`, Arrow →
    native DDL render rules) is **required for `kind: database` and
    forbidden for `kind: api`**. The read map validates against the
    existing `type-map/latest.json` schema; the write map is validated
    semantically only (`--semantic-only`) because the published schema
    is read-direction-only today — its `canonical` constraint rejects
    write-direction regex matchers (contract gap raised upstream). The
    validator derives the rule direction from the filename. A leftover
    `type-map.json` sibling is an error with a migration pointer.
  - Write-map rules invert the matcher/render sides: `canonical`
    matches (regex with ECMA named captures for parameterized types)
    and `native` renders (`${name}` substitutions backed by those
    captures). New `type-map-write-coverage` validator probes the write
    map against the full canonical vocabulary and warns on gaps
    (legitimate only behind a `render_column_type` dialect override).
  - Read-map regex patterns are now matched against UPPERCASED,
    whitespace-collapsed natives (mirroring the engine): author
    patterns uppercase; lowercase regex literals warn; exact rules are
    normalized automatically; the endpoint coverage walker normalizes
    natives before matching.
  - `tls-consistency` now recognizes connector-defined verification
    modes (`VERIFY_CA` / `VERIFY_IDENTITY` alongside
    `verify-ca` / `verify-full`).
  - A type map validated under a filename that is neither
    `type-map-read.json` nor `type-map-write.json` now warns that the
    rule direction defaulted to read (a misplaced write map's
    write-direction checks would otherwise vanish silently).
- **Database connectors are installable Python packages.**
  `db-connector-creator` now authors the package files alongside the
  JSON artifacts: `connector.py` (`{Name}Dialect(SqlDialect)` +
  `{Name}Connector(GenericSQLConnector)`; CDK imports only),
  `__init__.py`, `requirements.txt` (this connector's drivers only),
  and `pyproject.toml` (`analitiq-connector-{connector_id}`, dynamic
  deps, entry points named `{connector_id}` under both source and
  destination groups). `CreatorOutput` gained `type_map_read`,
  `type_map_write`, and `package_files` (replacing `type_map`). The
  schema validator stays JSON-only — package files are registry CI's
  responsibility. New reference: `connector-spec-db/spec-connector-package.md`.
- **Driver selection decision order.** New
  `connector-spec-db/spec-driver-selection.md` + reworked
  `TransportTypeMapper`: (1) first-class ADBC driver → (2) Arrow Flight
  SQL → (3) async SQLAlchemy + native bulk path in the connector class
  → (4) async SQLAlchemy batched INSERT, never the JDBC bridge.
  SQLAlchemy drivers must be async — guidance and examples moved from
  `mysql+asyncmy` to `mysql+aiomysql` (with the `pymysql<1.2` pin
  noted). `ProviderFacts` (database branch) gained
  `adbc_driver_package`, `flight_sql_endpoint`, `bulk_load_protocol`,
  `async_sqlalchemy_driver`.
- **Examples mirror the engine reference packages** (engine workspace
  `connectors/{id}/` is source of truth): postgres/mysql/snowflake
  read+write maps copied verbatim (uppercase natives; postgres/mysql
  read `JSON`/`JSONB` as `Utf8` — text on the wire — while Snowflake
  keeps `VARIANT`/`OBJECT`/`ARRAY` → `Json`); the mysql example adopts
  MySQL's native TLS vocabulary (`DISABLED`…`VERIFY_IDENTITY`),
  interpreted by the dialect's `build_tls_connect_arg` (the SSL-mode
  vocabulary is now documented as connector-defined).
- **Snowflake example switched to ADBC; MongoDB example dropped.** The
  snowflake reference example now uses `transport_type: "adbc"` with the
  `snowflake` driver and `db_kwargs` (no DSN), per the driver-selection
  decision order (Snowflake is a first-class ADBC system); the prior
  sync `sqlalchemy` / `snowflake` transport violated the async-only
  rule. The MongoDB example is removed — there is no async SQLAlchemy
  MongoDB driver and a document store does not fit the SQL transport
  contract, so it should not have shipped as a `sqlalchemy` example.
- `connector-drift-classifier` diffs both map files independently; the
  type-map drift categories apply per file/direction.
- `connector-provider-researcher`: `docs_url` is now optional. When the
  user does not supply one, the researcher uses WebSearch to locate the
  provider's official documentation (first-party domain only) and
  reports the URL it used. WebSearch never serves as a source of
  facts — extraction still happens exclusively from first-party
  documentation pages fetched with WebFetch.
- **Validator surface hardening.** Several `--semantic-only` silent-pass
  cases now emit structured findings:
  - New `endpoint-annotations` validator id surfaces malformed
    `(native_type, arrow_type)` pairs when an api-endpoint file is
    validated directly (was only checked via the connector path).
  - `expression-resolver` now rejects nodes with non-string `ref` /
    `template` / `function` values and multi-keyed value-expression
    nodes (e.g. both `ref` and `function` present).
  - `phase-resolvability` emits warnings when a `connection_contract.
    inputs[*]` declaration has unknown `storage` or unknown `phase`,
    or when `inputs` / `post_auth_outputs` / `transports` is
    present-but-non-object.
  - `dsn-binding` flags missing `dsn.kind`, unknown `dsn.kind`,
    non-dict `bindings`, non-string `template`, and non-string
    `transport_ref`.
  - `tls-consistency` flags non-dict `ssl_mode` and non-list
    `ssl_mode.enum`.
  - `type-map-rule` flags non-string `canonical`, non-string `native`,
    unknown rule keys, and rules missing required keys.
  - New top-level warnings for unrecognized document shapes (e.g.
    a DB endpoint validated against `--semantic-only`, scalar /
    list-of-non-dict roots, empty arrays, legacy type-map shapes).
  - Annotation walkers now recurse through every
    `JsonSchemaPropertyNode` keyword (`prefixItems`,
    `additionalProperties`, `patternProperties`, `$defs`,
    `definitions`, `dependentSchemas`, `not`, `if`/`then`/`else`,
    `contains`, `propertyNames`, `unevaluatedItems`,
    `unevaluatedProperties`) instead of only `properties` / `items` /
    `oneOf|anyOf|allOf` — tuple-typed responses and reusable sub-schemas
    are now visible to coverage and asymmetric-pair analysis.
  - `finding()` now uses `raise ValueError` (not `assert`) so validator
    id and severity invariants survive `python -O`. Per-validator
    crash handler in `run_semantic_validators` tags crashes with the
    failing `vid` so orchestrators route correctly.
  - The `Diagnostics.validator` enum (`io-contracts.md`) gained
    `endpoint-annotations`.

- **Type maps now standalone files.** Aligned the plugin with the
  published `https://schemas.analitiq.ai/type-map/latest.json` contract:
  - Connector JSON no longer carries an embedded `type_maps` block; the
    connector schema rejects unknown fields at the top level.
  - Authors emit a sibling `{connector_id}/definition/type-map.json` — a
    top-level array of `{match, native, canonical}` rules (renamed
    from `method` → `match`; dropped the `native_to_arrow.rules`
    wrapper). Required and non-empty for both API and DB.
  - Regex rules may template the canonical with `${name}` substitutions
    backed by ECMA-262 `(?<name>…)` named capture groups in `native`
    (e.g. `Decimal128(${precision}, ${scale})`). The validator
    translates to Python's `(?P<…>)` form internally.
  - Schemaless natives (`jsonb`, `VARIANT`, `OBJECT`, `ARRAY`, MySQL
    `json`, MongoDB documents) map to `"Json"`. `Object` / `List` are
    endpoint-only markers (carry sibling `properties` / `items`) and
    are accepted as narrowings of a `Json`-resolved rule in API
    coverage.
  - `scripts/validate_connector.py` rewritten: drops the
    connector-body `type_maps` path; loads sibling `type-map.json`;
    walks API endpoints for `(native_type, arrow_type)` pairs and
    asserts each `native_type` resolves to the field's declared
    `arrow_type` (rendering templated canonicals before comparison);
    new `type-map-rule` validator enforces `exact`-no-template,
    `regex`-named-capture, and duplicate-rule rules. New schema URL
    `https://schemas.analitiq.ai/type-map/latest.json` added to the
    validator agent and orchestrator phase 5.
  - All 7 endpoint fixtures (including the new `api_endpoints_arrow_mismatch`)
    and the 11 spec examples (5 DB — postgresql, postgresql-adbc,
    mysql, snowflake, mongodb — plus 6 API) migrated into per-example
    subdirectories, each with a sibling `type-map.json`. The API
    examples gained a minimal `endpoints/` directory so the strict
    per-kind contract holds.
- **ADBC transport added.** `TransportTypeMapper` now recognizes `adbc`
  as the preferred `transport_type` for databases in the engine's ADBC
  driver enum (closed: `postgresql`, `snowflake`, `bigquery`). ADBC
  transports carry required `driver` (the enum identifier) plus the
  shared `dsn` url-template shape and/or `db_kwargs` (at least one
  required). `db_kwargs` values may be value expressions; TLS for ADBC
  is expressed via `db_kwargs` entries (e.g. `adbc.postgresql.sslmode`)
  — the generic `tls` block is SQLAlchemy-only. `db-connector-creator`
  step 2, `connector-spec-db` SKILL, and `spec-dsn-bindings.md`
  updated. New `examples/postgresql-adbc/` reference example shipped
  alongside the existing `examples/postgresql/` (sqlalchemy) variant.
- **Plugin now authors `connector_id`.** Per the published connector
  contract, `connector_id` is an optional author-supplied identifier
  (UUID, slug, or any non-empty string); when omitted, the registry
  assigns one. This plugin always emits it so the directory name and
  the identifier are the same value, and there's no rewrite layer
  between the local `{connector_id}/` output and the contract path
  `connectors/{connector_id}/definition/`. The `alias` field is gone
  entirely — the slug now lives only in `connector_id`. Reserved-field
  rules narrowed to `created_at` / `updated_at` only. Drift table adds
  four new categories: `type-map-rule-added` (minor),
  `type-map-rule-reordered` (patch — only when the reorder doesn't
  change first-match resolution), `type-map-rule-removed` (major), and
  `type-map-canonical-changed` (major — an existing `native` now
  resolves to a different canonical).
- API endpoint authoring realigned with the published
  `api-endpoint/latest.json` schema (engine PR #51):
  - Endpoint documents now carry `endpoint_id` (pattern
    `^[a-z0-9][a-z0-9_-]*$`); the previous top-level `alias` is
    rejected. `endpoint-creator` agent, `io-contracts.md`
    `EndpointCreatorOutput`, on-disk filename convention
    (`endpoints/{endpoint_id}.json`), and the four api-endpoint test
    fixtures updated accordingly.
  - `operations.write` is now a mode-keyed map (`insert` / `upsert`
    only); each mode block requires `request` + `input.schema` and
    accepts optional `batching` (`{max_records ≥ 2}`), `params`,
    `response`. `endpoint-creator` step 4 and `connector-spec-api`
    SKILL cross-reference rewritten.
  - `operations.read` guidance restated to match the published shape:
    `request` and `response` required; `params`, `pagination`,
    `replication` optional. Dropped the `from_param` wording — the
    schema binds request shape directly via value expressions, with
    `Param` objects declared under `params`.
  - `scripts/validate_connector.py` type-map coverage walker now
    descends into `operations.write.<mode>.input.schema` and
    `operations.write.<mode>.params[*]` instead of treating `write`
    as a single op. Added three fixture trees + tests covering
    fully-covered, uncovered, and multi-mode (insert + upsert)
    write endpoints — including JSON-pointer assertions to guard
    against the per-mode loop or `input.schema` path regressing.
  - `endpoint-creator` write `response` bullet now describes
    `affected_records` / `generated_keys` / `error.{code,message,details}`
    / `metadata` / `success_when` instead of just saying "optional".
  - Repo-root `CLAUDE.md` `Key Concepts` and `Connector Directory
    Structure` sections updated from `{endpoint-alias}.json` to
    `{endpoint_id}.json` so the project-level concept doc no longer
    contradicts the plugin docs.
- `type_maps.native_to_arrow.rules[].canonical` values aligned with the
  fully-qualified Apache Arrow vocabulary used by the pipeline-builder's
  endpoint `arrow_type` contract. Renamed every `"canonical": "String"`
  to `"canonical": "Utf8"` (24 occurrences across postgresql / mysql /
  snowflake / mongodb examples and the api-endpoints test fixtures) —
  `String` is not a member of the published Arrow type set; the canonical
  UTF-8 string type is `Utf8`. `skills/connector-spec-db/spec-type-maps.md`
  rewritten with a new "`canonical` value forms by `method`" section.
  Policy:
  - `exact` rules with a non-parameterized canonical (`Utf8`, `Boolean`,
    `Int64`, `Date32`, `Binary`, …) emit the bare name.
  - `exact` rules with a parameterized canonical must encode the
    database's documented default precision / scale / unit literally —
    bare `Decimal128` / `Timestamp` / `Time64` from `exact` rules are
    now wrong. Snowflake `NUMBER`/`DECIMAL` → `Decimal128(38, 0)`,
    `TIME` → `Time64(NANOSECOND)`, `TIMESTAMP_NTZ` →
    `Timestamp(NANOSECOND)`, `TIMESTAMP_LTZ`/`TIMESTAMP_TZ` →
    `Timestamp(NANOSECOND, UTC)`; MongoDB `decimal` (BSON Decimal128,
    34-digit IEEE 754) → `Decimal128(34, 0)`, `date` (ms epoch UTC) →
    `Timestamp(MILLISECOND, UTC)`; api `date-time` →
    `Timestamp(MICROSECOND, UTC)`.
  - `regex` rules matching parameterized natives (`^NUMERIC\(…\)$`,
    `^timestamp(…)?$`) emit the base PascalCase name (`Decimal128`,
    `Timestamp`) and the runtime carries parameters from the captured
    native at discovery time. Temporary contract until `type_maps`
    supports capture-group templating in `canonical`.
  Snowflake / MongoDB examples and the `api_endpoints_covered` test
  fixture rewritten accordingly. PostgreSQL / MySQL regex rules
  unchanged.

## [3.0.1] - 2026-05-12

### Removed
- `connector_schema_version` dropped from the `reserved-field`
  validator's `RESERVED_FIELDS` set, its matching parametrized test
  case, and every doc reference (agent prompts, skill, README,
  top-level `CLAUDE.md`, `metadata-and-versioning.md`). The published
  `connector/latest.json` schema no longer carries the field, so
  guarding against it was dead weight. Mirrors the sibling
  `analitiq-pipeline-builder` cleanup that landed in PR #27.

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
  directory matching `{connector_id}/` already exists, the build halts and
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
- Standardized on `{connector_id}/` as the connector output directory name
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
  `{connector_id}/definition/endpoints/`, the `type-map-coverage` validator
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
