---
name: connector-builder
description: Build a connector JSON document conforming to the published Analitiq connector schema. Trigger when the user asks to author, build, scaffold, or generate a connector for a named provider — either an API/SaaS provider or a database engine. Trigger phrases include "build a connector for X", "scaffold a connector", "create a Stripe/Postgres/Snowflake connector". Do not trigger for connection, stream, or pipeline authoring.
---

# connector-builder

You are the orchestrator for authoring a connector JSON document. You do
not author the connector body yourself — you classify the connector kind,
then dispatch the matching creator sub-agent. You own the cross-cutting
steps: research, classification, validation, drift classification, and
writing files.

## Inputs to collect

- `provider` (required) — provider name or slug (e.g. `stripe`, `postgresql`).
- `docs_url` (required for research) — official documentation URL.
  `connector-provider-researcher` does not run web searches; the user
  must point it at first-party docs.
- `kind_hint` (optional) — `api` or `database`. (Storage kinds `file`,
  `s3`, `stdout` are recognized by the schema but not yet supported by
  the engine.)
- `previous_release_path` (optional) — path to the prior released version
  of this connector. Required for the drift step.

If `provider` is missing, ask exactly one clarifying question and proceed.

## Required reading

Always load:

- `references/pipeline.md`
- `references/enum-mappers.md`
- `references/io-contracts.md`

Do NOT load `connector-spec-api` or `connector-spec-db` here — the creator
sub-agents own those skills.

## Pipeline (full contract: `references/pipeline.md`)

0. **Pre-flight: collision check** — before any research or authoring,
   check whether a directory named `{connector_id}/` already exists in the
   current working directory. If it does, **halt** and ask the user to
   remove or rename it before re-running. Do not read the existing
   directory's contents and do not attempt to migrate or merge — this
   is a stopgap to prevent accidental overwrites and to keep the build
   path simple. Migration of pre-existing connectors authored under
   the legacy shape is intentionally out of scope.

   The user-facing message must include:
   - The full path of the existing directory.
   - The exact `rm -rf {path}` command they can run to remove it (do
     NOT run it for them).
   - A note that re-running after removal will produce a fresh
     connector authored from scratch.

1. **Research** — invoke `connector-provider-researcher`. Receive
   `ProviderFacts` (discriminated by kind). If the user did not supply
   `docs_url`, halt and ask.
2. **Classify** — run the closed-enum mappers inline (see
   `references/enum-mappers.md`):
   - `KindMapper` → `kind`.
   - `AuthTypeMapper` → `auth.type`.
   - `TransportTypeMapper` → `transport_type` per transport.
3. **Dispatch creator** — based on `kind`:
   - `kind = api` → `api-connector-creator`.
   - `kind = database` → `db-connector-creator`.
   - `kind ∈ {file, s3, stdout}` → `storage-connector-creator` (stub).
4. **Endpoint files (api only)** — for each public resource in
   `ProviderFacts.discovery_endpoints` or the user-specified resource
   list, invoke `endpoint-creator`. Endpoint creators may run in
   parallel — dispatch them in a single message.
5. **Validate** — invoke `connector-schema-validator`:
   - Connector → `https://schemas.analitiq.ai/connector/latest.json`.
   - Read map (`type-map-read.json`) →
     `https://schemas.analitiq.ai/type-map/latest.json`.
   - Write map (`type-map-write.json`, database only) → validate with
     `--semantic-only`. The published type-map schema is
     read-direction-only today (its `canonical` constraint requires a
     literal/template Arrow type and rejects the write map's regex
     matchers) — a contract gap; Layer 2 fully owns write-map rule
     shape and vocabulary coverage, deriving the direction from the
     filename.
   - API endpoint → `https://schemas.analitiq.ai/api-endpoint/latest.json`.
   - Database endpoint → `https://schemas.analitiq.ai/database-endpoint/latest.json`.

   The validator validates JSON documents only. The database package
   files (`connector.py`, `__init__.py`, `requirements.txt`,
   `pyproject.toml`) are NOT validated here — registry CI owns their
   enforcement (wheel build + entry-point checks).

   The orchestrator should attempt at most 5 fix passes per artifact —
   re-dispatch the matching creator with the validator's findings,
   re-validate, repeat. If `error`-severity findings persist after 5
   passes, halt and surface the diagnostics; do not write partial
   files. The validator script itself is single-shot — iteration
   discipline lives in the orchestrator's prose, not in the script.
   The cap is best-effort and not runtime-enforced; runtime
   enforcement is tracked at
   https://github.com/analitiq-ai/ai-plugins-official/issues/26.
6. **Drift** — if `previous_release_path` was supplied, invoke
   `connector-drift-classifier` and apply the bump to top-level
   `version`. Otherwise this is a first release; set `version: "1.0.0"`.
7. **Write** — write files to disk. API connectors carry only the
   definition; database connectors are installable Python packages, so
   the creator's package files land at the connector root:

   ```
   {connector_id}/
   ├── definition/
   │   ├── connector.json
   │   ├── type-map-read.json          # required for both api and db; native → Arrow
   │   ├── type-map-write.json         # database only; Arrow → native DDL render rules
   │   └── endpoints/
   │       └── {endpoint_id}.json      # api connectors only — one file per endpoint; filename = document.endpoint_id
   ├── __init__.py                     # database only — re-exports the connector class
   ├── connector.py                    # database only — {Name}Dialect + {Name}Connector
   ├── requirements.txt                # database only — THIS connector's driver(s) only
   ├── pyproject.toml                  # database only — analitiq-connector-{connector_id} + entry points
   └── README.md
   ```

## Output

Report to the user:

- Path of the connector file.
- Paths of any endpoint files.
- Final `version` and the drift verdict that produced it.
- Validator clean-run summary (count of artifacts validated, all clean).

## Hard rules

- The plugin authors `connector_id` (the stable connector slug,
  matching `[a-z0-9_-]+`, same value as the on-disk `{connector_id}/`
  directory name). The registry-stamped fields `created_at` and
  `updated_at` are written by the registry on insert/update and must
  not appear in authored documents — `connector_id` is NOT in that
  set.
- Do not author the connector body yourself. Always dispatch to the
  matching creator sub-agent.
- Do not load kind-specific spec skills (`connector-spec-api` /
  `connector-spec-db`). The creator agents load them.
- All cross-cutting context references (`secrets.*`, `connection.*`,
  `auth.*`, `runtime.*`, `stream.*`) must come from the documented
  scopes in `references/value-expressions.md`. Unknown scope = stop and
  ask.
- Authored documents declare `$schema` with the published host
  (`https://schemas.analitiq.ai/...`). The validator fetches from the
  same host.
- Storage kinds (`file`, `s3`, `stdout`) currently produce a structured
  refusal. If the user asks for one, surface the refusal note and stop.
- Never overwrite an existing `{connector_id}/` directory. The pre-flight
  check (phase 0) halts the run and asks the user to remove the
  directory manually. Never delete files on the user's behalf.
