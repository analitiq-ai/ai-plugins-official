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
- `docs_url` (optional, preferred) — official documentation URL. When
  omitted, `connector-provider-researcher` locates the provider's
  official docs via WebSearch; facts are still extracted from
  first-party documentation pages only.
- `kind_hint` (optional) — `api` or `database`. (Storage kinds `file`,
  `s3`, `stdout` are recognized by the schema but not yet supported by
  the engine.)
- `mode` (optional) — `build` (default), `update`, or `validate`. See
  **Modes** below.
- `connector_path` (required for `update` / `validate`) — path to the
  existing connector directory. Its directory name is the `connector_id`
  and its `connector.json` carries the authoritative slug; read both up
  front (this is the target artifact, not spec material). Unused in
  `build` mode.
- `previous_release_path` (optional) — path to the prior released version
  of this connector, read as the read-only baseline for the drift step.
  In `update` mode it defaults to `connector_path` when not supplied.

If `provider` is missing in `build` / `update` mode, ask exactly one
clarifying question and proceed. In `validate` mode the connector is
identified by `connector_path`, so `provider` is optional.

## Modes

The orchestrator runs in one of three modes (input `mode`, default
`build`). `build` and `update` share phases 1–5 and differ only at
phases 0, 6, and 7; `validate` runs only phase 0 → phase 5 (report-only,
no fix loop), skipping phases 1–4 and 6–7.

- **`build`** (default) — author a fresh connector. Phase 0 halts if a
  `{connector_id}/` directory already exists.
- **`update`** — the connector already exists and its upstream system
  has changed. Re-author from *current* docs (phases 1–5 run normally),
  then diff the fresh draft against the existing connector to set the
  new version (phase 6 is required), and regenerate the tree (phase 7).
  The existing connector is read **only** as the drift baseline — it is
  never edited in place, and the version is bumped from the prior
  release, never reset to `1.0.0`. Run inside a VCS checkout so the
  regeneration is reviewable via `git diff`. Connector content is
  treated as fully reproducible from `ProviderFacts` + creator logic;
  non-reproducible hand edits to a connector are not preserved across an
  update (known limitation).
- **`validate`** — read-only. Skip phases 1–4 and 6–7; run phase 5
  (validation) over the on-disk documents and report the diagnostics. Do
  not research, author, fix, or write. To fix reported findings, re-run
  in `update` mode.

## Required reading

Always load:

- `references/pipeline.md`
- `references/enum-mappers.md`
- `references/io-contracts.md`

Do NOT load `connector-spec-api` or `connector-spec-db` here — the creator
sub-agents own those skills.

## Pipeline (full contract: `references/pipeline.md`)

0. **Pre-flight** — branch on `mode` before any research or authoring:
   - **`build`** — check whether a directory named `{connector_id}/`
     already exists in the current working directory. If it does,
     **halt** and ask the user to remove or rename it before re-running.
     Do not read the existing directory's contents and do not attempt to
     migrate or merge — this is a stopgap to prevent accidental
     overwrites and to keep the build path simple. Migration of
     pre-existing connectors authored under the legacy shape is
     intentionally out of scope. The user-facing message must include
     the full path of the existing directory, the exact `rm -rf {path}`
     command they can run to remove it (do NOT run it for them), and a
     note that re-running after removal will produce a fresh connector
     authored from scratch.
   - **`update`** — `connector_path` points at the existing connector.
     Read its directory name and `connector.json` `connector_id` up front
     (the target artifact, not spec material) and record it as the
     read-only drift baseline (the default `previous_release_path`).
     Proceed to phase 1; do not edit it in place — phase 7 regenerates
     the tree. If research/authoring later yields a `connector_id` that
     differs from `connector_path`'s, **halt** and surface the mismatch
     rather than writing a divergent tree (a changed slug is a new
     connector, not an update). If `connector_path` does not exist, fall
     back to `build` semantics and tell the user.
   - **`validate`** — read the on-disk documents under `connector_path`
     (`definition/connector.json`, `definition/type-map-read.json`,
     `definition/type-map-write.json` when present, and
     `definition/endpoints/*.json`) and skip directly to phase 5. No
     research, authoring, or writing. If `connector_path` does not exist,
     halt and tell the user there is nothing to validate.

1. **Research** — invoke `connector-provider-researcher`. Receive
   `ProviderFacts` (discriminated by kind). Pass `docs_url` when the
   user supplied one; otherwise the researcher locates the official
   docs itself and reports the URL it used.
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
     `https://schemas.analitiq.ai/type-map-read/latest.json`.
   - Write map (`type-map-write.json`, database only) →
     `https://schemas.analitiq.ai/type-map-write/latest.json`. Both maps
     run the full Layer 1 + Layer 2 pass; the validator derives the
     direction from the filename. Do not pass `--semantic-only`.
   - API endpoint → `https://schemas.analitiq.ai/api-endpoint/latest.json`.
   - Database endpoint → `https://schemas.analitiq.ai/database-endpoint/latest.json`.

   The validator validates JSON documents only. The database package
   files (`connector.py`, `__init__.py`, `requirements.txt`,
   `pyproject.toml`) are NOT validated here — registry CI owns their
   enforcement (wheel build + entry-point checks).

   In `validate` mode, run the validator once over the on-disk
   documents, report the resulting `Diagnostics`, and stop — there is no
   fix loop and no creator re-dispatch (phases 1–4 were skipped, so there
   is no `CreatorOutput` to revise). The fix loop below applies to
   `build` and `update` only.

   In `build` / `update` mode the orchestrator should attempt at most 5
   fix passes per artifact — re-dispatch the matching creator with the
   validator's findings and the artifacts it produced on the prior pass
   (`CreatorOutput` / `EndpointCreatorOutput`), re-validate, repeat. The
   creator — not the orchestrator — decides whether each finding is a
   real defect or a validator false positive; it owns the spec. Pass
   `Diagnostics.findings` verbatim and do not pre-filter, pre-diagnose,
   or read spec material to interpret them yourself. If `error`-severity
   findings persist after 5
   passes, halt and surface the diagnostics; do not write partial
   files. The validator script itself is single-shot — iteration
   discipline lives in the orchestrator's prose, not in the script.
   The cap is best-effort and not runtime-enforced; runtime
   enforcement is tracked at
   https://github.com/analitiq-ai/ai-plugins-official/issues/26.
6. **Drift** — the classifier reads `previous_version` from
   `previous_release_path` and returns the computed `next_version`; set
   the connector's top-level `version` to that `next_version` directly
   (do not recompute the semver yourself). This `version` is the
   connector's own release semver, owned by `connector-drift-classifier`
   — unrelated to the plugin package version, which this repo bumps via
   PR labels. The classifier needs a `current_path` to diff, so stage the
   freshly-authored draft to a temporary path first.
   - **`update`** — required: invoke `connector-drift-classifier` with
     `previous_release_path` = the existing connector and `current_path`
     = the staged draft, and apply the returned `next_version` (never
     reset to `1.0.0`).
   - **`build`** — if `previous_release_path` was supplied, invoke
     `connector-drift-classifier` the same way (staged draft as
     `current_path`) and apply `next_version`; otherwise this is a first
     release — set `version: "1.0.0"`.
7. **Write** — write files to disk. In `update` mode the regenerated
   files replace the existing connector tree (its prior files were read
   as the drift baseline in phase 6, never edited in place); report that
   the tree was regenerated and recommend reviewing `git diff` before
   committing. API connectors carry only the definition; database
   connectors are installable Python packages, so the creator's package
   files land at the connector root:

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
- **The orchestrator never diagnoses findings and never reads spec
  material.** Do not load or read the kind-specific spec skills
  (`connector-spec-api` / `connector-spec-db`), their example/reference
  files, or the published JSON Schemas, and never fetch a schema URL to
  interpret a failure. When the validator returns findings, do not
  reason about the schema yourself — re-dispatch the owning
  creator/endpoint agent with the findings verbatim and let it triage
  and fix. Your only specs are the orchestrator references
  (`pipeline.md`, `io-contracts.md`, `enum-mappers.md`, plus
  `value-expressions.md` for scope lookups).
- All cross-cutting context references (`secrets.*`, `connection.*`,
  `auth.*`, `runtime.*`, `stream.*`) must come from the documented
  scopes in `references/value-expressions.md`. Unknown scope = stop and
  ask.
- Authored documents declare `$schema` with the published host
  (`https://schemas.analitiq.ai/...`). The validator fetches from the
  same host.
- Storage kinds (`file`, `s3`, `stdout`) currently produce a structured
  refusal. If the user asks for one, surface the refusal note and stop.
- In `build` mode, never overwrite an existing `{connector_id}/`
  directory — the phase-0 check halts the run and asks the user to
  remove it manually. In `update` mode, regeneration replaces the
  existing tree by design (its prior files are read as the drift
  baseline first, never edited in place); rely on the user's VCS
  checkout for safety. Never delete files outside the connector
  directory on the user's behalf.
