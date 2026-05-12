# I/O contracts between orchestrator and agents

Every cross-agent payload is a JSON object that conforms to one of
these shapes. The orchestrator validates them in code (using the
matching JSON Schema below) before passing them to the next phase.

## `PipelineFacts` (output of `pipeline-provider-researcher`)

Discriminated by `source_kind` and `destination_kind`. Each kind has its
own required sub-shape.

```jsonc
{
  "pipeline_alias": "wise_to_postgresql",     // matches ^[a-z0-9][a-z0-9_-]*$
  "display_name": "Wise to PostgreSQL",
  "description": "…",
  "source": {
    "connector_alias": "wise",                // resolves in DIP registry
    "kind": "api",                            // "api" | "database"
    "selected_endpoints": ["transfers"],      // alias list; required
    "replication": {
      "method": "incremental",                // "full_refresh" | "incremental"
      "cursor_field": "updated_at"            // required when method == incremental
    }
  },
  "destination": {
    "connector_alias": "postgresql",
    "kind": "database",                       // "api" | "database"
    "schema": "public",                       // database only
    "write": {
      "mode": "upsert",
      "conflict_keys": [["id"]]               // required when mode requires it
    }
  },
  "schedule": {
    "type": "manual",                         // "manual" | "interval" | "cron"
    "timezone": "UTC"                         // IANA name; default UTC
  },
  "engine_overrides": null,                   // EngineConfig sub-shape or null
  "runtime_overrides": null                   // RuntimeConfig sub-shape or null
}
```

## `CreatorOutput` (output of every creator agent)

Each creator agent returns the JSON it would write, plus optional notes.
The orchestrator handles disk I/O.

```jsonc
{
  "entity": "pipeline",                       // "pipeline" | "stream" | "connection" | "database_endpoint"
  "alias": "wise_to_postgresql",
  "document": { /* the authored JSON, $schema set, no server-managed fields */ },
  "secondary_files": [                        // optional — e.g., .secrets templates
    {"path": ".secrets/credentials.json", "content": { /* … */ }}
  ],
  "notes": []                                 // human-readable rationale / caveats
}
```

For unsupported cases (e.g., a connector kind the engine can't run),
the creator returns:

```jsonc
{
  "entity": "stream",
  "alias": null,
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
    {"kind": "stream_added", "alias": "balances"},
    {"kind": "write_mode_changed", "from": "insert", "to": "upsert"},
    {"kind": "mapping_target_added", "stream": "transfers", "path": "currency"}
  ],
  "summary": "1 stream added; 1 write-mode change; 1 mapping target added."
}
```
