# Orchestration pipeline

Phase-by-phase contract for the `connector-builder` orchestrator. Loaded
on demand by the orchestrator skill.

## Phases

### 0. Pre-flight: collision check

Before any other work, check whether a directory named `{connector_id}/`
already exists in the current working directory.

- If it does NOT exist → proceed to phase 1.
- If it DOES exist → halt the run and surface a structured warning.

The warning must include:

- The full absolute path of the existing directory.
- The exact `rm -rf {path}` command the user can run to remove it.
  The orchestrator MUST NOT delete the directory itself — manual
  removal is required so the user has a chance to inspect or back up
  whatever's there.
- A note that re-running after removal produces a fresh connector
  authored from scratch (no migration of legacy connector shapes).

**Why this exists.** The plugin authors connectors against the
published schema contract. Pre-existing connectors authored against
older shapes (e.g. with `placeholders` arrays or a `manifest.json`,
or with the plugin pre-rewriting on top of an existing tree) are not
migrated by this plugin. Stopping early avoids partial-state writes
and keeps the build path simple. A future migrator agent could relax
this check; for now, manual removal is the contract.

**Failure mode.** If the user reports they cannot remove the directory
(permissions, dirty tree under VCS, etc.), do not attempt workarounds.
Surface the OS-level error and let the user resolve it before
re-running.

### 1. Research

Invoke `connector-provider-researcher` with `provider`, optional
`kind_hint`, and the official-docs URL when the user supplied one
(when omitted, the researcher locates the official docs via WebSearch
and reports the URL it used). Receive a `ProviderFacts` JSON object
discriminated by `kind`.

**Input:** `provider`, `kind_hint?`, `docs_url?`.
**Output:** `ProviderFacts` (plus the docs URLs actually used).
**Failure mode:** if the researcher cannot access or locate official
docs, halt and ask the user for a URL or manually-supplied facts.

### 2. Classify

Run the closed-enum mappers inline (see `enum-mappers.md`):

- `KindMapper` → `kind` (one of `api`, `database`).
- `AuthTypeMapper` → `auth.type`.
- `TransportTypeMapper` → `transport_type` per transport.

Storage kinds (`file`, `s3`, `stdout`) are accepted by the schema but not
yet supported by the engine. If the user explicitly asked for one,
dispatch to `storage-connector-creator` (which currently returns a
structured refusal); otherwise fail closed and ask.

### 3. Dispatch creator

Based on `kind`:

- `kind = api` → invoke `api-connector-creator` with `ProviderFacts` plus
  classifications.
- `kind = database` → invoke `db-connector-creator` with the same.
- `kind ∈ {file, s3, stdout}` → invoke `storage-connector-creator` (stub).

Receive a `CreatorOutput` JSON object containing the assembled connector
body and type map(s). For `kind = database` it additionally carries the
`package_files` block (`connector.py`, `__init__.py`, `requirements.txt`,
`pyproject.toml` contents) — the connector is an installable Python
package and the creator owns all of its files.

### 4. Endpoint files (api only)

For each public resource in `ProviderFacts.discovery_endpoints` or the
user-specified resource list, invoke `endpoint-creator`. Endpoint creators
may run in parallel — dispatch them in a single message.

Database connectors do not ship endpoint files; their schema/table
combinations are connection-scoped and discovered at runtime via
`resource_discovery`.

### 5. Validate

Invoke `connector-schema-validator` with the connector document and
`schema_url=https://schemas.analitiq.ai/connector/latest.json`. Also
validate the standalone `type-map-read.json` against
`https://schemas.analitiq.ai/type-map/latest.json`, and — for database
connectors — `type-map-write.json` with `--semantic-only`: the
published type-map schema is read-direction-only today (its
`canonical` constraint rejects the write map's regex matchers — a
contract gap, raised upstream); Layer 2 fully owns write-map rule
shape and vocabulary coverage. The validator derives the rule
direction from the filename, so write the maps under their exact
filenames before standalone validation, or validate via the connector
document so the sibling walk picks them up. For each endpoint
document, invoke the validator with the kind-specific URL:

- API endpoint → `https://schemas.analitiq.ai/api-endpoint/latest.json`.
- Database endpoint (when applicable in future) →
  `https://schemas.analitiq.ai/database-endpoint/latest.json`.

The validator validates JSON documents only — the database package
files (`connector.py`, `__init__.py`, `requirements.txt`,
`pyproject.toml`) are enforced by registry CI (wheel build,
entry-point checks), not by this pipeline.

The orchestrator should attempt at most 5 fix passes per artifact —
re-dispatch the matching creator with the validator's findings,
re-validate, repeat. If `error`-severity findings persist after 5
passes, halt and surface the diagnostics; do not write partial files.
The validator script is single-shot; iteration discipline lives in
the orchestrator's prose, not in the script. The cap is best-effort
and not runtime-enforced; runtime enforcement is tracked at
https://github.com/analitiq-ai/ai-plugins-official/issues/26.

### 6. Drift

If `previous_release_path` was supplied, invoke
`connector-drift-classifier`. Apply the returned bump to the top-level
`version` of the assembled document.

If `previous_release_path` was not supplied, this is a first release; set
`version` to `1.0.0`.

### 7. Write

Write the connector document, type map(s), package files (database
only), and any endpoint files to disk at predictable paths. The
connector root IS the Python package for database connectors:

```
{connector_id}/
├── definition/
│   ├── connector.json
│   ├── type-map-read.json          # required for both api and db; native → Arrow
│   ├── type-map-write.json         # database only; Arrow → native DDL render rules
│   └── endpoints/
│       └── {endpoint_id}.json      # api connectors only — one file per endpoint; filename = document.endpoint_id
├── __init__.py                     # database only — re-exports the connector class
├── connector.py                    # database only — {Name}Dialect(SqlDialect) + {Name}Connector(GenericSQLConnector)
├── requirements.txt                # database only — THIS connector's driver(s) only
├── pyproject.toml                  # database only — analitiq-connector-{connector_id}; entry points named {connector_id}
└── README.md
```

Never write a `type-map.json` — that pre-split filename is dead to the
engine and the validator rejects it with a migration finding.

## Failure modes

- Research timeout: ask user for offline-supplied facts or a different docs URL.
- Classification ambiguity: fail closed; ask the user to confirm.
- Validator stuck: surface findings; do not write incomplete files.
- Drift classifier rolls back to `none`: treat as first release.
