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
- `pipeline_alias` (required) — stable slug `[a-z0-9_-]+`; immutable; used to
  derive the placeholder pipeline UUID and the on-disk directory.
- `replication_method` (optional, default per source capability) — one of
  `full_refresh`, `incremental`. Required `cursor_field` if `incremental`.
- `write_mode` (optional, default per destination capability) — for API
  destinations, one of the endpoint's `operations.write` keys; for
  database destinations, `insert` or `upsert` (the latter requires
  `conflict_keys`).
- `schedule_type` (optional, default `manual`) — `manual` / `interval` / `cron`.
- `previous_release_path` (optional) — path to the prior released directory
  of this pipeline. Required for the drift step.

If any required input is missing, ask exactly one clarifying question and
proceed once the user answers.

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
  dev/prod schema-host situation.

Do NOT load `pipeline-spec`, `stream-spec`, `connection-spec`, or
`endpoint-spec` here — the creator sub-agents own those.

## Pipeline (full contract: `references/pipeline.md`)

0. **Pre-flight: collision check** — before any research or authoring,
   check whether `pipelines/{pipeline_alias}/`, `connections/{alias}/`
   for either side, or `connectors/{alias}/` for either side already
   exist in the current working directory. If any do, **halt** and ask
   the user to remove them before re-running. Do not migrate legacy-shape
   files.

   The user-facing message must include:
   - The full paths of the existing directories.
   - The exact `rm -rf <path>` commands they can run.
   - A note that re-running after removal will produce fresh, schema-
     aligned artifacts from scratch.

1. **Research** — invoke `pipeline-provider-researcher`. Receive
   `PipelineFacts` (discriminated by `source_kind` and `destination_kind`).
   If the user did not supply required inputs, halt and ask.

2. **Connectors** — invoke `registry-browser` once for source and once
   for destination, in parallel (single message, two tool calls). Each
   call writes `connectors/{alias}/` from the DIP registry. The
   downloaded `connector.json` is read-only — never modify it.

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

5. **Connections** — invoke `connection-creator` once per side, in
   parallel. Each writes:
   - `connections/{alias}/connection.json` — validates against
     `connection/latest.json`.
   - `connections/{alias}/.secrets/credentials.json` — template the user
     fills in. Reference each secret as `secrets/{alias}/{key}` in
     `connection.secret_refs`.

6. **Endpoint discovery (database connections only)** — invoke
   `private-endpoint-creator` once per database connection. Three sub-
   modes, sequential per connection but parallel across connections:
   `discover-schemas` → user picks → `discover-tables` → user picks →
   `create-endpoints`. Each created endpoint validates against
   `database-endpoint/latest.json`. Output:
   `connections/{alias}/endpoints/{database_object.schema}-{database_object.name}.json`.

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
    - Pipeline → `https://schemas.analitiq.work/pipeline/latest.json`.
    - Stream → `https://schemas.analitiq.work/stream/latest.json`.
    - Connection → `https://schemas.analitiq.work/connection/latest.json`.
    - Database endpoint → `https://schemas.analitiq.work/database-endpoint/latest.json`.

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
- Never emit the legacy three-section mapping (`source_to_generic`,
  `generic_to_destination`, `assignments_hash`, `type_mapping_assignments_hash`).
  Authored mapping is `assignments`-only; the registry computes the rest.
- All cross-document references between pipeline / stream / connection /
  endpoint must resolve consistently. The `pipeline-stream-consistency`
  validator enforces this; pass `--bundle-root .` when validating the
  stitched pipeline.
- Authored documents declare `$schema` with the **production** host
  (`https://schemas.analitiq.ai/...`). The validator currently *fetches*
  from the **dev** host (`https://schemas.analitiq.work/...`). See
  `references/schema-hosts.md`.
- Never overwrite an existing `pipelines/{alias}/`, `connections/{alias}/`,
  or `connectors/{alias}/` directory. The pre-flight check (phase 0) halts
  and asks the user to remove the directory manually. Never delete files
  on the user's behalf.
