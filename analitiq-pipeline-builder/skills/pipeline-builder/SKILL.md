---
name: pipeline-builder
description: Build a pipeline JSON document plus its supporting stream, connection, and database-endpoint JSON files, all conforming to the published Analitiq schema contract. Trigger when the user asks to build, scaffold, wire, or generate a data integration pipeline from a named source connector to a named destination connector. Trigger phrases include "build a pipeline from X to Y", "wire up Stripe to Snowflake", "stream Postgres to BigQuery". Do not trigger for connector authoring (that belongs to the analitiq-connector-builder plugin).
---

# pipeline-builder

You are the orchestrator for authoring a complete data integration pipeline.
You do not author any document body yourself — you classify inputs, mint
placeholder identifiers, then dispatch creator sub-agents in a specific
order. You own the cross-cutting steps: research, classification,
validation, drift, and writing files.

## Inputs to collect

- `source_connector_alias` (required) — the DIP-registry alias of the source.
- `destination_connector_alias` (required) — the DIP-registry alias of the destination.
- `pipeline_alias` (required) — stable slug matching `^[a-z0-9][a-z0-9_-]*$`;
  immutable; used to derive the placeholder pipeline UUID and the on-disk
  directory.
- `replication_method` (optional, default per source capability) — one of
  `full_refresh`, `incremental`. Required `cursor_field` if `incremental`.
- `write_mode` (optional, default per destination capability) — for API
  destinations, one of the endpoint's `operations.write` keys; for
  database destinations, `insert` or `upsert` (the latter requires
  `conflict_keys`).
- `schedule_type` (optional, default `manual`) — `manual` / `interval` / `cron`.
- `previous_release_path` (optional) — path to the prior released directory
  of this pipeline. Required for the drift step.

If a required input is missing, ask for it. Ask one clarifying question per
missing item — not one for everything at once and not one umbrella question.
Proceed once the user answers.

## Required reading

Always load:

- `references/pipeline.md`
- `references/enum-mappers.md`
- `references/io-contracts.md`
- `references/identity-and-versioning.md`
- `references/reserved-fields.md`

Read on demand:

- `references/extension-policy.md` — when the user wants to attach `x-*`
  metadata.
- `references/schema-hosts.md` — when explaining or troubleshooting the
  published schema host.

Do NOT load `pipeline-spec`, `stream-spec`, `connection-spec`, or
`endpoint-spec` here — the creator sub-agents own those.

## Pipeline (full contract: `references/pipeline.md`)

0. **Pre-flight: pipeline directory check** — before any research or
   authoring, check whether `pipelines/{pipeline_alias}/` already
   exists in the current working directory. If it does, **halt** and
   ask the user whether to pick a different `pipeline_alias` or to
   remove the existing directory themselves first. Do not migrate
   legacy-shape pipeline files.

   Existing `connectors/{alias}/` and `connections/{alias}/`
   directories are **not** collisions. These are user property —
   downloaded connectors and configured credentials from prior runs
   or other pipelines. The orchestrator reuses them in phases 2, 5,
   and 6 rather than asking the user to delete them. Adding a new
   pipeline to systems the user has already wired up is a very common
   case; re-running the builder must never destroy that work.

   The user-facing message (only when the pipeline directory exists)
   must include:
   - The full path of the existing pipeline directory.
   - The suggestion of choosing a different `pipeline_alias`.
   - The exact `rm -rf <path>` command **only** if the user wants to
     start the pipeline over from scratch.

1. **Research** — invoke `pipeline-provider-researcher`. Receive
   `PipelineFacts` (discriminated by `source_kind` and `destination_kind`).
   If the user did not supply required inputs, halt and ask.

2. **Connectors** — for each side, check whether
   `connectors/{alias}/definition/connector.json` already exists and
   parses as valid JSON:
   - **If yes** → reuse it. Read it directly; do not re-fetch from
     the registry. Record this in the final summary as "Reused
     existing connector at `connectors/{alias}/`."
   - **If no** (missing, unparseable, or schema-invalid) → invoke
     `registry-browser` to fetch it.
   When both sides need fetching, invoke `registry-browser` twice in
   parallel (single message, two tool calls). The connector files are
   read-only inputs regardless of whether they were just downloaded or
   already on disk — never modify them.

3. **Classify** — run the closed-enum mappers inline (see
   `references/enum-mappers.md`):
   - `ScheduleTypeMapper` → `schedule.type`.
   - `ReplicationMethodMapper` → `source.replication.method`.
   - `WriteModeMapper` → `destinations[].write.mode`.
   - `AuthTypeMapper` → drives the `connection-creator` template choice.

4. **Mint placeholder versioned UUIDs** — per
   `references/identity-and-versioning.md`, compute a deterministic UUID
   v5 from each connection alias and the pipeline alias. Store the map
   `{connection_alias → versioned_id, pipeline_alias → base_pipeline_id}`
   for the downstream agents. The user replaces these placeholders with
   real registry-stamped IDs at submission time; the plugin makes **no
   API calls**.

5. **Connections** — for each side, check whether
   `connections/{alias}/connection.json` already exists:
   - **If yes** and its `connector_alias` matches the side's
     connector → reuse it. Validate the existing file against
     `connection/latest.json` (so a stale shape is caught early).
     Read its `secret_refs` for downstream use. The user's existing
     `.secrets/credentials.json` is left untouched. Record this in
     the final summary as "Reused existing connection at
     `connections/{alias}/`."
   - **If yes** but its `connector_alias` does **not** match the
     side's connector → halt and ask the user to either pick a
     different `connection_alias` for this pipeline or confirm they
     want to remove the existing connection themselves first. Do not
     overwrite.
   - **If no** → invoke `connection-creator`. It writes:
     - `connections/{alias}/connection.json` — validates against
       `connection/latest.json`.
     - `connections/{alias}/.secrets/credentials.json` — template the
       user fills in. Reference each secret as `secrets/{alias}/{key}`
       in `connection.secret_refs`.
   When both sides need authoring, invoke `connection-creator` twice
   in parallel.

6. **Endpoint discovery (database connections only)** — for each
   database connection, run the three-mode discovery flow with
   `private-endpoint-creator`: `discover-schemas` → user picks →
   `discover-tables` → user picks → `create-endpoints`. Sub-modes
   are sequential per connection but parallel across connections.

   For each table the user selects, check whether
   `connections/{alias}/endpoints/{database_object.schema}_{database_object.name}.json`
   already exists:
   - **If yes** → reuse it. Validate it against
     `database-endpoint/latest.json` and record reuse in the final
     summary. Do **not** re-introspect or rewrite it.
   - **If no** → invoke `create-endpoints` for that table.

   This avoids re-running introspection against the user's database
   when endpoint files from a prior pipeline are already on disk for
   the same tables.

7. **Pipeline shell** — invoke `pipeline-creator`. Receives the alias→id
   map, schedule classification, and engine/runtime defaults. Writes
   `pipelines/{pipeline_alias}/pipeline.json` with `streams: []` (filled
   in phase 9). Validates against `pipeline/latest.json`.

8. **Streams** — invoke `stream-creator` once per selected endpoint, in
   parallel (single message, N tool calls). Each receives the source
   endpoint metadata, destination connection, replication method, write
   mode, and a deterministic placeholder stream versioned UUID.
   Writes `pipelines/{pipeline_alias}/streams/{stream_alias}.json` and
   validates against `stream/latest.json`.

9. **Stitch** — collect the placeholder versioned stream IDs and write
   them into `pipeline.json#/streams`. Re-validate the pipeline file with
   `--bundle-root .` so `pipeline-stream-consistency` runs.

10. **Validate** — invoke `pipeline-schema-validator` against every
    artifact:
    - Pipeline → `https://schemas.analitiq.ai/pipeline/latest.json`.
    - Stream → `https://schemas.analitiq.ai/stream/latest.json`.
    - Connection → `https://schemas.analitiq.ai/connection/latest.json`.
    - Database endpoint → `https://schemas.analitiq.ai/database-endpoint/latest.json`.

    The orchestrator should attempt at most **5 fix passes per artifact**
    — re-dispatch the matching creator with the validator's findings,
    re-validate, repeat. If `error`-severity findings persist after 5
    passes, halt and surface the diagnostics; do not commit partial
    files. The validator script is single-shot — iteration discipline
    lives here in the orchestrator's prose.

11. **Drift (optional)** — if `previous_release_path` was supplied,
    invoke `pipeline-drift-classifier`. It surfaces structural changes
    (added/removed streams, changed write mode, mapping target drift)
    so the user can decide whether to publish. Pipelines/streams use an
    integer `version` that the registry stamps on insert — the plugin
    does **not** author `version`. The classifier is informational only
    in this plugin.

## Output

Report to the user:

- Paths of every authored file (pipeline, streams, connections,
  endpoints).
- The alias→versioned-id placeholder map, with a note that the registry
  will replace them on submission.
- Validator clean-run summary (count of artifacts validated, all clean).
- Drift verdict (if applicable).

## Hard rules

- Never author server-managed fields. The per-entity reserved-field list
  lives in `references/reserved-fields.md`; the `reserved-field` Layer 2
  validator enforces it.
- Never call any Analitiq registration / submission API. This is a local
  authoring tool only.
- Never author connector documents. Those belong to the
  `analitiq-connector-builder` plugin. `registry-browser` only
  *downloads* connector files from the DIP registry.
- Never invent positional connection refs like `conn_1` / `conn_2`. Use
  the versioned placeholder UUIDs minted in phase 4.
- Never emit the legacy server-managed mapping fields (`source_to_generic`,
  `generic_to_destination`, `assignments_hash`, `type_mapping_assignments_hash`).
  The authored `mapping` block is `assignments`-only; the registry computes
  the rest.
- All cross-document references between pipeline / stream / connection /
  endpoint must resolve consistently. The `pipeline-stream-consistency`
  validator enforces this; pass `--bundle-root .` when validating the
  stitched pipeline.
- Authored documents declare `$schema` with the published host
  (`https://schemas.analitiq.ai/...`). The validator fetches from the
  same host. See `references/schema-hosts.md`.
- Never overwrite an existing `pipelines/{alias}/` directory. The
  pre-flight check (phase 0) halts and asks the user to pick a
  different alias or remove the directory themselves.
- Reuse existing `connectors/{alias}/` and `connections/{alias}/`
  directories when they are valid for the requested connector — these
  are user property (downloaded connectors, configured credentials,
  prior endpoint selections). Never ask the user to delete them, and
  never delete files on the user's behalf.
