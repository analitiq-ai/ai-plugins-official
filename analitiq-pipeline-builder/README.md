# Analitiq Pipeline Builder Plugin

Claude Code plugin that authors **pipeline**, **stream**, **connection**, and
**database-endpoint** JSON documents conforming to the published Analitiq schema
contract at [`schemas.analitiq.ai`](https://schemas.analitiq.ai). Downloads connectors from the
[Analitiq DIP Registry](https://github.com/analitiq-ai/analitiq-dip-registry)
and wires them into complete pipelines. Does **not** create connectors and does
**not** call any registration APIs — it is a local authoring tool only.

## What it does

Given a source connector slug and a destination connector slug, the plugin:

1. Researches user intent (replication method, write mode, schedule, naming).
2. Downloads the source + destination connectors from the DIP registry.
3. Authors a `connection.json` per side with a single `values` envelope —
   secret entries carry a `"<see .secrets/credentials.json>"` placeholder and
   the plugin emits a sibling `.secrets/credentials.json` template the user
   fills in.
4. For database connections, introspects the live database to discover schemas
   and tables, then authors `database-endpoint` documents per selected table.
5. Authors a `pipeline.json` shell that references the connections by their
   `connection_id` UUIDs.
6. Authors one `stream.json` per selected endpoint, dispatched in parallel.
7. Validates everything against the published JSON schemas plus a layer of
   semantic validators (schedule shape, runtime ranges, endpoint-ref shape,
   mapping shape, filter operators, column uniqueness, pipeline↔stream
   consistency, status lifecycle).
8. Writes files to disk at predictable paths only when every artifact passes.

**Usage:** Launch Claude Code and say *"build a pipeline from &lt;source&gt; to
&lt;destination&gt;"*.

## Architecture

```
pipeline-builder (skill, orchestrator)
├── pipeline-provider-researcher  # collects PipelineFacts (no WebSearch)
├── registry-browser              # downloads source + destination connectors
├── connection-creator            # authors connection/latest.json + .secrets/
├── private-endpoint-creator      # DB only: introspects + authors database-endpoint/latest.json
├── pipeline-creator              # authors pipeline/latest.json shell
├── stream-creator                # authors stream/latest.json (one per endpoint, parallel)
├── pipeline-schema-validator     # JSON Schema + semantic validation
└── pipeline-drift-classifier     # surfaces structural diff against previous_release
```

The orchestrator owns classification and cross-cutting steps. Each creator
agent owns the authoring vocabulary for its entity via a dedicated spec skill
(`pipeline-spec`, `stream-spec`, `connection-spec`, `endpoint-spec`).

## Supported entities

| Entity | Schema | Authored by |
|---|---|---|
| Pipeline | `https://schemas.analitiq.ai/pipeline/latest.json` | `pipeline-creator` |
| Stream | `https://schemas.analitiq.ai/stream/latest.json` | `stream-creator` |
| Connection | `https://schemas.analitiq.ai/connection/latest.json` | `connection-creator` |
| Database endpoint (private) | `https://schemas.analitiq.ai/database-endpoint/latest.json` | `private-endpoint-creator` |
| API endpoint | `https://schemas.analitiq.ai/api-endpoint/latest.json` | not authored — comes from the connector document |
| Connector | `https://schemas.analitiq.ai/connector/latest.json` | not authored — owned by `analitiq-connector-builder` |

## Validation

The plugin includes a Python validator (`scripts/validate_pipeline.py`) that
runs:

1. **JSON Schema validation** (Draft 2020-12) against the published schema
   selected by `--entity {pipeline|stream|connection|database_endpoint}`.
2. **Semantic validators** for rules JSON Schema can't express:
   - `reserved-field` — no server-managed fields in authored docs.
   - `schedule-shape` — manual / interval / cron field exclusivity; IANA
     timezone parses.
   - `runtime-ranges` — engine vcpu/memory, runtime buffer/batching, error
     handling retries.
   - `endpoint-ref-shape` — `scope ∈ {connector, connection}` with
     `scope=connection` reserved for database endpoints; destination refs
     unique.
   - `mapping-shape` — exactly one of `expression` / `constant` per assignment;
     `expression.op == "get"` (v1); unique target paths; validation rules
     reference mapped fields.
   - `filter-operators` — database vs API operator vocabularies; unary
     operators omit `value`.
   - `column-uniqueness` — column name uniqueness, `ordinal_position`
     uniqueness, primary-key resolution against declared columns.
   - `pipeline-stream-consistency` (with `--bundle-root`) — every referenced
     stream's `pipeline_id` matches the parent pipeline's `pipeline_id`;
     endpoint-ref connection IDs are members of `pipeline.connections`.
   - `status-lifecycle` — `status=active` requires runnable streams.

Run directly:

```bash
python scripts/validate_pipeline.py \
  --entity pipeline \
  --document path/to/pipeline.json \
  --bundle-root path/to/project
```

Output is a single `Diagnostics` JSON object. Exit `0` iff `passed: true`.

Tests live under `tests/pipeline_validator/`. Run with `pytest`.

## Schema host

- The validator fetches schemas from `https://schemas.analitiq.ai`.
- Authored documents declare `$schema` with the same host — the URL is
  locked by a `const` inside the published schema.

## File output

For each successfully built pipeline:

```
connectors/                         # downloaded by registry-browser, read-only
├── <source-slug>/
│   ├── definition/
│   │   ├── connector.json
│   │   └── endpoints/              # API connectors only
│   └── README.md
└── <destination-slug>/...

connections/
├── <connection-slug>/
│   ├── connection.json             # validates against connection/latest.json
│   ├── .secrets/
│   │   ├── credentials.json        # template the user fills in
│   │   └── client.json             # OAuth2 only
│   └── endpoints/                  # database connections only
│       └── <endpoint-slug>.json    # validates against database-endpoint/latest.json

pipelines/
└── <pipeline-slug>/
    ├── pipeline.json               # validates against pipeline/latest.json
    └── streams/
        └── <stream-slug>.json      # validates against stream/latest.json
```

### Identity model: UUIDs inside, slugs on disk

The plugin authors **RFC-4122 UUIDs** for `pipeline_id`, `stream_id`,
and `connection_id` and threads them through every cross-document
reference. `connector_id` and `endpoint_id` are **slugs** (the
connector's registry slug; the endpoint's stable `^[a-z0-9][a-z0-9_-]*$`
identifier). Directory names on disk stay human-readable slugs and are
independent of the UUID identity stored inside each document — the
slug is purely for file organization. The plugin makes no API calls;
the registry can also assign UUIDs on ingest if the plugin omits them.

### Connection secrets workflow

Connection documents use a single flat `values` envelope. For inputs
whose connector contract bucket is `secrets`, the plugin writes a
human-readable placeholder string into `values` and emits a
`.secrets/credentials.json` template the user fills in. The user (or
CI) merges secret values from `.secrets/` into the document's `values`
block before submitting the connection to the registry. The registry
never reads `.secrets/` directly.

### Reusing existing connectors and connections

Adding a new pipeline to systems the user has already wired up is a
very common case. The orchestrator reuses what's already on disk:

- **`connectors/<connector-slug>/`** — if `definition/connector.json`
  is already present and parses, it is reused (no registry re-fetch).
- **`connections/<connection-slug>/`** — if `connection.json` is
  already present and its `connector_id` matches the side's connector,
  the connection (and its existing `.secrets/credentials.json`) is
  reused as-is. The orchestrator reads its `connection_id` UUID and
  uses it in downstream cross-references. If the `connector_id`
  doesn't match, the orchestrator halts and asks the user to pick a
  different `connection_slug` or remove the existing file themselves.
- **`connections/<connection-slug>/endpoints/*.json`** — endpoint
  files for tables already discovered in a prior run are reused; only
  newly selected tables run database introspection.

The only directory that blocks the orchestrator is
`pipelines/<pipeline-slug>/` itself. If it exists, the user is asked
to pick a different `pipeline_slug` or remove the directory themselves
first — pipelines are per-build artifacts, not shared state. The
orchestrator never deletes files on the user's behalf and never
overwrites a connection's `.secrets/`.

## Installation

```bash
claude plugin add ./analitiq-pipeline-builder
```

## Links

- [Analitiq DIP Registry](https://github.com/analitiq-ai/analitiq-dip-registry) — connectors authored by the sibling `analitiq-connector-builder` plugin.
- [Schema contracts](https://github.com/analitiq-ai/analitiq-infra/tree/main/docs/schema-contracts) — authoritative shape specs.
- [Published schemas](https://schemas.analitiq.ai) — the JSON Schemas the validator runs against.

## License

Apache 2.0 — see [LICENSE](LICENSE).
