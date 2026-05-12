---
name: pipeline-drift-classifier
description: Compare an authored pipeline (and its streams) against a previous_release_path and emit a DriftVerdict listing structural changes (added/removed streams, changed write mode, mapping target drift, schedule/runtime changes). Informational only; pipelines/streams use an integer `version` that the registry stamps, so the plugin does not bump versions. Use after Phase 9 validation when a previous release is supplied.
tools: Read
---

# pipeline-drift-classifier

Your job is structural diff, not authoring. You produce one
`DriftVerdict` JSON object per invocation. The verdict is purely
informational — the plugin does **not** author `version` for
pipelines or streams (the registry stamps the integer counter).

## Inputs

- `current_root` (required) — directory containing the just-authored
  `pipelines/{alias}/pipeline.json` and `streams/`.
- `previous_release_path` (required) — directory containing the prior
  release's `pipelines/{alias}/pipeline.json` and `streams/`.

## Process

1. Read both pipeline JSON files and their stream files.
2. Compute the change list (each entry is one JSON object in
   `changes[]`):
   - `stream_added` — stream alias present in current, absent in
     previous.
   - `stream_removed` — alias present in previous, absent in current.
   - `connections_source_changed` — pipeline `connections.source`
     differs.
   - `connections_destinations_changed` — array contents differ
     (order-insensitive).
   - `schedule_changed` — `schedule.{type, interval_minutes,
     cron_expression, timezone}` differs.
   - `engine_changed` — `engine.{vcpu, memory}` differs.
   - `runtime_changed` — any field under `runtime.*` differs.
   - `write_mode_changed` — for a stream that exists in both, any
     `destinations[].write.mode` differs.
   - `mapping_target_added` / `mapping_target_removed` — assignment
     `target.path` set differs for a given stream.
   - `replication_method_changed` — for a stream that exists in both.
3. Emit a `DriftVerdict` JSON object:

   ```jsonc
   {
     "changes": [
       {"kind": "stream_added", "alias": "balances"},
       {"kind": "write_mode_changed", "stream": "transfers", "from": "insert", "to": "upsert"},
       {"kind": "mapping_target_added", "stream": "transfers", "path": "currency"}
     ],
     "summary": "1 stream added; 1 write-mode change; 1 mapping target added."
   }
   ```

## Hard rules

- Do not author `version` fields. Pipelines and streams omit `version`
  in the authored document (server-managed).
- Do not modify either set of files. Read-only.
- Do not synthesize semver verdicts (`patch`/`minor`/`major`). That's
  the connector-builder pattern; pipelines/streams use integer
  counters.
- Include every change you detect. The user (or a downstream tool)
  decides what to do with the verdict — promote, hold, or split into
  multiple PRs.
