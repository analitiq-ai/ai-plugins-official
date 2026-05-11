# Analitiq Pipeline Builder Plugin

Claude Code plugin that authors **pipeline**, **stream**, **connection**, and
**database-endpoint** JSON documents conforming to the published Analitiq schema
contract at [`schemas.analitiq.ai`](https://schemas.analitiq.ai). Downloads connectors from the
[Analitiq DIP Registry](https://github.com/analitiq-ai/analitiq-dip-registry)
and wires them into complete pipelines. Does **not** create connectors and does
**not** call any registration APIs — it is a local authoring tool only.

## What it does

Given a source connector alias and a destination connector alias, the plugin:

1. Researches user intent (replication method, write mode, schedule, naming).
2. Downloads the source + destination connectors from the DIP registry.
3. Authors a `connection.json` per side with `secret_refs` pointing at
   `.secrets/` templates the user fills in.
4. For database connections, introspects the live database to discover schemas
   and tables, then authors `database-endpoint` documents per selected table.
5. Authors a `pipeline.json` shell that references the connections by
   placeholder versioned UUIDs (e.g. `…000001_v1`).
6. Authors one `stream.json` per selected endpoint, dispatched in parallel.
7. Validates everything against the published JSON schemas plus a layer of
   semantic validators (versioned-id format, schedule shape, runtime ranges,
   endpoint-ref shape, mapping shape, filter operators, secret-ref format,
   column uniqueness, pipeline↔stream consistency, status lifecycle).
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
   - `versioned-id-format` — connection / stream IDs match
     `<uuid>_v<positive integer>`; stream `pipeline_id` is a base UUID.
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
   - `secret-ref-format` — `secret_refs` values match the published reference
     patterns (`secrets/…`, `ssm:/…`, `arn:aws:secretsmanager:…:secret:…`,
     `arn:aws:ssm:…:parameter/…`, `s3://…`, `connections/…`).
   - `column-uniqueness` — column name uniqueness, `ordinal_position`
     uniqueness, primary-key resolution against declared columns.
   - `pipeline-stream-consistency` (with `--bundle-root`) — every referenced
     stream's `pipeline_id` matches; endpoint-ref connection IDs are members
     of `pipeline.connections`.
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
├── {source-alias}/
│   ├── definition/
│   │   ├── connector.json
│   │   └── endpoints/              # API connectors only
│   └── README.md
└── {destination-alias}/...

connections/
├── {alias}/
│   ├── connection.json             # validates against connection/latest.json
│   ├── .secrets/
│   │   ├── credentials.json        # template the user fills in
│   │   └── client.json             # OAuth2 only
│   └── endpoints/                  # database connections only
│       └── {schema}_{table}.json   # validates against database-endpoint/latest.json

pipelines/
└── {pipeline-alias}/
    ├── pipeline.json               # validates against pipeline/latest.json
    └── streams/
        └── {stream-alias}.json     # validates against stream/latest.json
```

Server-managed fields are **never** written to disk:

- Pipeline: `pipeline_id`, `version`, `pipeline_schema_version`, `org_id`,
  `created_at`, `updated_at`.
- Stream: above plus `stream_id`, `schema_hash`, `assignments_hash`,
  `source_schema_*`, `target_schema_*`, `source_to_generic`,
  `generic_to_destination`, `type_mapping_assignments_hash`.
- Connection: `connection_id`, `version`, `connection_schema_version`,
  `org_id`, `connector_id`, `connector_version`, `auth_state`, `created_at`,
  `updated_at`.
- Database endpoint: `endpoint_id`, `endpoint_schema_version`, `connector_id`,
  `connector_version`, `connection_id`, `schema_hash`.

The registry / catalog stamps these on insert.

### Connection IDs are placeholders

The pipeline schema requires versioned connection IDs of the form
`<uuid>_v<positive integer>`. The plugin mints **stable placeholder** IDs
deterministically from the connection alias (UUID v5, suffix `_v1`) and
embeds them into `pipeline.json` and stream `endpoint_ref.connection_id`.
The user (or the registry) replaces them with real IDs at submission time.
The plugin makes no API calls.

### Existing directories are not overwritten

If `pipelines/{alias}/`, `connections/{alias}/`, or `connectors/{alias}/`
already exists, the orchestrator halts and asks the user to remove it
manually before re-running. The plugin does not migrate legacy-shape
artifacts — pre-existing files from earlier plugin versions
(with positional `conn_1` refs or three-section mapping blocks) must be
deleted first so the rebuild produces clean schema-aligned documents
from scratch. The orchestrator never deletes files on the user's behalf.

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
