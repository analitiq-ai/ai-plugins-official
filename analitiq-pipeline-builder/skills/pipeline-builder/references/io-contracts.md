# I/O contracts between orchestrator and agents

Every cross-agent payload is a JSON object that conforms to one of
these shapes. The orchestrator validates them in code (using the
matching JSON Schema below) before passing them to the next phase.

## `PipelineFacts` (output of `pipeline-provider-researcher`)

Discriminated by `source_kind` and `destination_kind`. Each kind has its
own required sub-shape.

```jsonc
{
  "pipeline_slug": "wise_to_postgresql",        // matches ^[a-z0-9][a-z0-9_-]*$; directory name only
  "display_name": "Wise to PostgreSQL",
  "description": "…",
  "source": {
    "connector_id": "wise",                     // connector slug; resolves in DIP registry
    "connection_slug": "wise",                  // directory name for connections/<slug>/
    "kind": "api",                              // "api" | "database"
    "selected_endpoints": ["transfers"],        // endpoint_id list; required
    "replication": {
      "method": "incremental",                  // "full_refresh" | "incremental"
      "cursor_field": "updated_at"              // required when method == incremental
    }
  },
  "destination": {
    "connector_id": "postgresql",
    "connection_slug": "postgresql",
    "kind": "database",                         // "api" | "database"
    "schema": "public",                         // database only
    "write": {
      "mode": "upsert",
      "conflict_keys": [["id"]]                 // required when mode requires it
    }
  },
  "schedule": {
    "type": "manual",                           // "manual" | "interval" | "cron"
    "timezone": "UTC"                           // IANA name; default UTC
  },
  "engine_overrides": null,                     // EngineConfig sub-shape or null
  "runtime_overrides": null                     // RuntimeConfig sub-shape or null
}
```

## `MintedIdentities` (orchestrator-local, phase 3)

After classification, the orchestrator generates UUIDs and bundles them
so creator agents can cross-reference consistently.

```jsonc
{
  "pipeline_id": "11111111-1111-4111-8111-111111111111",
  "connections": {
    "source":      {"connection_id": "22222222-…", "connection_slug": "wise"},
    "destinations": [{"connection_id": "33333333-…", "connection_slug": "postgresql"}]
  },
  "streams": [
    {"stream_id": "44444444-…", "stream_slug": "transfers_to_warehouse", "endpoint_id": "transfers"}
  ]
}
```

Reused on-disk connections contribute their **existing** `connection_id`
UUID (read from the on-disk `connection.json`) instead of a freshly
generated one.

## `CreatorOutput` (output of every creator agent)

Each creator agent returns the JSON it would write, plus optional notes.
The orchestrator handles disk I/O.

```jsonc
{
  "entity": "pipeline",                       // "pipeline" | "stream" | "connection" | "database_endpoint"
  "directory_slug": "wise_to_postgresql",     // matching directory name under pipelines/ etc.
  "document": { /* the authored JSON, $schema set, no server-managed fields */ },
  "secondary_files": [                        // optional — e.g., .secrets templates
    {"path": ".secrets/credentials.json", "content": { /* … */ }}
  ],
  "notes": []                                 // human-readable rationale / caveats
}
```

The identity UUID (`pipeline_id`, `stream_id`, `connection_id`) lives
inside `document`; the orchestrator reads it from there for downstream
cross-references. Endpoint creators carry the slug identity in
`document.endpoint_id`.

For unsupported cases (e.g., a connector kind the engine can't run),
the creator returns:

```jsonc
{
  "entity": "stream",
  "directory_slug": null,
  "document": null,
  "notes": [
    "Storage-kind destinations (file/s3/stdout) are accepted by the schema but the engine does not yet execute them. The plugin declines to author a stream binding for this destination until engine support lands."
  ]
}
```

## `Diagnostics` (output of `scripts/validate_pipeline.py`)

```jsonc
{
  "passed": false,
  "findings": [
    {
      "validator": "schedule-shape",
      "severity": "error",
      "path": "/schedule",
      "message": "schedule.type='interval' requires interval_minutes; cron_expression must be absent.",
      "rule_doc": "shared/schedule.md"
    }
  ]
}
```

`severity ∈ {"error", "warning"}`. `passed` is `true` iff no `error`
findings exist (warnings allowed).

## `DriftVerdict` (output of `pipeline-drift-classifier`)

Informational only. The plugin does not author `version` (registry-
stamped integer counter). The verdict's role is to flag structural
changes the user should think about before publishing.

```jsonc
{
  "changes": [
    {"kind": "stream_added", "stream_slug": "balances"},
    {"kind": "write_mode_changed", "from": "insert", "to": "upsert"},
    {"kind": "mapping_target_added", "stream_slug": "transfers", "path": "currency"}
  ],
  "summary": "1 stream added; 1 write-mode change; 1 mapping target added."
}
```
