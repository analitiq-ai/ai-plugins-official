---
name: pipeline-builder
description: Build a pipeline JSON document plus its supporting stream, connection, and database-endpoint JSON files, all conforming to the published Analitiq schema contract. Trigger when the user asks to build, scaffold, wire, or generate a data integration pipeline from a named source connector to a named destination connector. Trigger phrases include "build a pipeline from X to Y", "wire up Stripe to Snowflake", "stream Postgres to BigQuery". Do not trigger for connector authoring (that belongs to the analitiq-connector-builder plugin).
---

# pipeline-builder

You are the orchestrator for authoring a complete data integration pipeline.
You do not author any document body yourself — you classify inputs, mint
UUID identities, then dispatch creator sub-agents in a specific order. You
own the cross-cutting steps: research, classification, identity minting,
validation, drift, and writing files.

## Inputs to collect

- `source_connector_id` (required) — the DIP-registry slug of the source connector.
- `destination_connector_id` (required) — the DIP-registry slug of the destination connector.
- `pipeline_slug` (required) — directory name matching `^[a-z0-9][a-z0-9_-]*$`;
  immutable; the on-disk pipeline directory (not the document's UUID identity).
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

Read on demand:

- `references/extension-policy.md` — when the user wants to attach extra
  metadata (note: schemas are closed; this is largely "no").
- `references/schema-hosts.md` — when explaining or troubleshooting the
  published schema host.
- `references/reserved-fields.md` — only when debugging a
  `reserved-field` finding from the validator. The spec skills and
  examples define what IS authored; this file enumerates what the
  validator catches if it leaks in.

Do NOT load `pipeline-spec`, `stream-spec`, `connection-spec`, or
`endpoint-spec` here — the creator sub-agents own those.

## Pipeline (full contract: `references/pipeline.md`)

0. **Pre-flight: pipeline directory check** — before any research or
   authoring, check whether `pipelines/<pipeline-slug>/` already
   exists in the current working directory. If it does, **halt** and
   ask the user whether to pick a different `pipeline_slug` or to
   remove the existing directory themselves first. Do not migrate
   legacy-shape pipeline files.

   Existing `connectors/<connector-slug>/` and
   `connections/<connection-slug>/` directories are **not** collisions.
   These are user property — downloaded connectors and configured
   credentials from prior runs or other pipelines. The orchestrator
   reuses them in phases 2, 4, and 5 rather than asking the user to
   delete them. Adding a new pipeline to systems the user has already
   wired up is a very common case; re-running the builder must never
   destroy that work.

   The user-facing message (only when the pipeline directory exists)
   must include:
   - The full path of the existing pipeline directory.
   - The suggestion of choosing a different `pipeline_slug`.
   - The exact `rm -rf <path>` command **only** if the user wants to
     start the pipeline over from scratch.

1. **Research** — invoke `pipeline-provider-researcher`. Receive
   `PipelineFacts` (discriminated by `source_kind` and `destination_kind`).
   If the user did not supply required inputs, halt and ask.

2. **Connectors** — for each side, check whether
   `connectors/<connector-slug>/definition/connector.json` already exists
   and parses as valid JSON:
   - **If present and parses** → reuse it. Read it directly; do not
     re-fetch from the registry. Record "Reused existing connector
     at `connectors/<connector-slug>/`" in the final summary. Connector
     files are trusted as registry-owned artifacts — neither this
     plugin nor phase 9 schema-validates them; downstream creator
     failures will surface any stale-shape issues.
   - **If present but does not parse** → halt and ask the user to
     fix or remove the file themselves. Do not invoke
     `registry-browser` against an existing-but-broken directory; it
     will refuse with `target_exists` and the user will get an
     unhelpful error.
   - **If absent** → invoke `registry-browser` to fetch it.

   When both sides need fetching, invoke `registry-browser` twice in
   parallel (single message, two tool calls).

   `registry-browser` returns one of two shapes:
   - `status: "downloaded"` → continue.
   - `status: "refused"` → branch on `reason`:
     - `target_exists` → defensive net (orchestrator's existence
       check should have prevented this call). Read the on-disk
       connector and continue, but flag the inconsistency for the
       user.
     - `registry_missing` → halt and surface `detail` verbatim.
       Suggest the user check the slug or author it via the
       `analitiq-connector-builder` plugin.
     - `fetch_failed` → halt and surface `detail` verbatim. The
       registry is reachable but the fetch did not succeed.

   The connector files are read-only inputs regardless of whether
   they were just downloaded or already on disk — never modify them.

3. **Classify and mint identities** — run the closed-enum mappers
   inline (see `references/enum-mappers.md`):
   - `ScheduleTypeMapper` → `schedule.type`.
   - `ReplicationMethodMapper` → `source.replication.method`.
   - `WriteModeMapper` → `destinations[].write.mode`.
   - `AuthTypeMapper` → drives the `connection-creator` template choice.

   Then mint UUIDs (`uuid.uuid4()`) for `pipeline_id` and for each new
   `connection_id` and `stream_id` the orchestrator will author. Reused
   on-disk connections contribute their existing `connection_id` UUIDs
   instead. Bundle the result as `MintedIdentities` (see
   `references/io-contracts.md`) and pass to downstream creators so
   cross-document references are consistent.

4. **Connections** — for each side, check whether
   `connections/<connection-slug>/connection.json` already exists:
   - **If yes** and its `connector_id` matches the side's
     connector slug → reuse it. Validate the existing file against
     `connection/latest.json` so a stale shape is caught early. If
     validation passes, record its `connection_id` UUID for downstream
     use, leave the user's `.secrets/credentials.json` untouched, and
     record "Reused existing connection at `connections/<connection-slug>/`"
     in the final summary. If validation **fails**, halt and
     surface the validator's findings (`path`, `message`,
     `rule_doc`) verbatim — the user needs to see what's broken to
     fix it. The orchestrator does not re-author the file (that
     would overwrite the user's `.secrets/`); the user must fix
     `connection.json` or remove it themselves before re-running.
   - **If yes** but its `connector_id` does **not** match the
     side's connector → halt and ask the user to either pick a
     different `connection_slug` for this pipeline or confirm they
     want to remove the existing connection themselves first. Do not
     overwrite.
   - **If no** → invoke `connection-creator`. It writes:
     - `connections/<connection-slug>/connection.json` — validates
       against `connection/latest.json`. Authors `connection_id` as
       the orchestrator-minted UUID, `connector_id` as the connector
       slug, and routes all input values into the single `values`
       envelope (secrets as `"<see .secrets/credentials.json>"`
       placeholders).
     - `connections/<connection-slug>/.secrets/credentials.json` —
       template the user fills in. The user (or CI) merges secret
       values from this file into `values` before submitting the
       connection.
   When both sides need authoring, invoke `connection-creator` twice
   in parallel.

5. **Endpoint discovery (database connections only)** — for each
   database connection, run the three-mode discovery flow with
   `private-endpoint-creator`: `discover-schemas` → user picks →
   `discover-tables` → user picks → `create-endpoints`. Sub-modes
   are sequential per connection but parallel across connections.

   For each table the user selects, check whether
   `connections/<connection-slug>/endpoints/<schema>_<name>.json`
   already exists:
   - **If yes** → reuse it. Validate it against
     `database-endpoint/latest.json` so a stale shape is caught
     early. If validation passes, record reuse in the final summary
     and do **not** re-introspect or rewrite the file. If validation
     **fails**, halt and surface the validator's findings (`path`,
     `message`, `rule_doc`) verbatim — the user needs to see what's
     broken to fix it. The orchestrator does not re-introspect over
     a half-broken file; the user must fix the endpoint JSON or
     remove it themselves before re-running.
   - **If no** → invoke `create-endpoints` for that table. Each
     endpoint document's `endpoint_id` slug typically matches its
     filename stem.

   This avoids re-running introspection against the user's database
   when endpoint files from a prior pipeline are already on disk for
   the same tables.

6. **Pipeline shell** — invoke `pipeline-creator`. Receives the minted
   `pipeline_id` UUID, the `connections.source` / `connections.destinations[]`
   UUIDs, schedule classification, and engine/runtime defaults. Writes
   `pipelines/<pipeline-slug>/pipeline.json` with `streams: []` (filled
   in phase 8). Validates against `pipeline/latest.json`.

7. **Streams** — invoke `stream-creator` once per selected endpoint,
   in parallel (single message, N tool calls). Each receives the
   source endpoint metadata, source + destination `connection_id`
   UUIDs, the minted `stream_id` UUID, replication method, write mode,
   and the parent `pipeline_id` UUID (written into stream `pipeline_id`).
   Writes `pipelines/<pipeline-slug>/streams/<stream-slug>.json` and
   validates against `stream/latest.json`.

8. **Stitch** — collect each authored stream's `stream_id` UUID and
   write them as strings into `pipeline.json#/streams`. Re-validate the
   pipeline file with `--bundle-root .` so
   `pipeline-stream-consistency` runs.

9. **Validate** — invoke `pipeline-schema-validator` against every
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

10. **Drift (optional)** — if `previous_release_path` was supplied,
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
- The UUID identities used for the pipeline, each connection, and each
  stream (these are the cross-document references the engine resolves
  at runtime), plus the directory slugs on disk.
- Validator clean-run summary (count of artifacts validated, all clean).
- Drift verdict (if applicable).

## Hard rules

- Never call any Analitiq registration / submission API. This is a local
  authoring tool only.
- Never author connector documents. Those belong to the
  `analitiq-connector-builder` plugin. `registry-browser` only
  *downloads* connector files from the DIP registry.
- Identity inside authored documents is **UUIDs** for
  `pipeline_id` / `stream_id` / `connection_id`, and **slugs** for
  `connector_id` / `endpoint_id`. Directory names use slugs. Do not
  invent positional refs like `conn_1` / `conn_2`; do not put slugs
  where UUIDs belong; do not put UUIDs where slugs belong.
- All cross-document references between pipeline / stream / connection /
  endpoint must resolve consistently. The `pipeline-stream-consistency`
  validator enforces this; pass `--bundle-root .` when validating the
  stitched pipeline.
- Authored documents declare `$schema` with the published host
  (`https://schemas.analitiq.ai/...`). The validator fetches from the
  same host. See `references/schema-hosts.md`.
- The published schemas are **closed** (`additionalProperties: false`).
  Do not author unknown fields, including `x-*` extension keys.
- Never overwrite an existing `pipelines/<pipeline-slug>/` directory.
  The pre-flight check (phase 0) halts and asks the user to pick a
  different slug or remove the directory themselves.
- Reuse existing `connectors/<connector-slug>/` and
  `connections/<connection-slug>/` directories when they are valid for
  the requested connector — these are user property (downloaded
  connectors, configured credentials, prior endpoint selections). Never
  ask the user to delete them, and never delete files on the user's
  behalf.
