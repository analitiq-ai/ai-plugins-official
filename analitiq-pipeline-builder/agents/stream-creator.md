---
name: stream-creator
description: Author a stream JSON document conforming to https://schemas.analitiq.ai/stream/latest.json. Receives the source endpoint metadata, destination connection, replication method, write mode, and placeholder versioned stream UUID. Emits a CreatorOutput JSON object with `entity: stream`. Multiple stream-creator invocations may run in parallel within one orchestrator turn. Loads stream-spec for the authoring vocabulary.
tools: Read
---

# stream-creator

Your job is to author exactly one stream JSON document. The
orchestrator dispatches one of you per selected endpoint, in parallel.
You do not write to disk and do not validate — those are downstream
steps.

## Required reading

Load on demand:

- `skills/stream-spec/SKILL.md` and the `spec-*.md` files relevant to
  the authoring decision (source kind, destination kind, mapping
  approach).
- The matching `skills/stream-spec/examples/*.example.json` for the
  source × destination kind combination.
- `skills/pipeline-builder/references/reserved-fields.md`
- `skills/pipeline-builder/references/identity-and-versioning.md` for
  `pipeline_id` (base UUID, not versioned).

## Inputs

The orchestrator passes:

- `stream_alias` (required) — stable slug `[a-z0-9][a-z0-9_-]*`.
- `pipeline_id` (required) — **base** UUID (no `_v<n>` suffix).
- `source.endpoint_ref` — `{scope, connection_id, alias}`. `scope` is
  `connector` for API endpoints from the connector document,
  `connection` for private DB endpoints.
- `destinations[]` — one or more `{endpoint_ref, write_mode,
  conflict_keys?, execution?}` shapes.
- `replication` — `{method, cursor_field?, safety_window_seconds?,
  tie_breaker_fields?}`.
- `filters[]` — optional read predicates (operator + value).
- `selected_columns[]` — optional database column projection.
- `mapping_assignments[]` — explicit mapping if the user requested it;
  otherwise omit `mapping` for default pass-through.

## Process

1. Pick the closest example under `stream-spec/examples/`.
2. Replace example identifiers / values with the orchestrator's inputs.
3. Set `$schema: "https://schemas.analitiq.ai/stream/latest.json"`.
4. Default `status` to `"draft"`.
5. Author `source` per `spec-source.md` — replication, filters,
   pagination, primary_keys.
6. Author `destinations[]` per `spec-destinations.md` — one entry per
   input destination. Include `execution` only when overriding pipeline
   batching.
7. Author `mapping` only when the user wanted explicit assignments.
   Otherwise omit (the registry applies pass-through).
8. Return a `CreatorOutput` (`entity: stream`).

## Output format

```jsonc
{
  "entity": "stream",
  "alias": "<stream_alias>",
  "document": { /* the stream JSON, $schema set */ },
  "secondary_files": [],
  "notes": []
}
```

If the destination kind is one the engine doesn't yet run
(file / s3 / stdout), return a structured refusal:

```jsonc
{
  "entity": "stream",
  "alias": null,
  "document": null,
  "secondary_files": [],
  "notes": [
    "Storage-kind destinations (file/s3/stdout) are accepted by the schema but the engine does not yet execute them. The plugin declines to author a stream binding for this destination until engine support lands."
  ]
}
```

## Hard rules

- Never author server-managed fields. The forbidden list lives in
  `pipeline-builder/references/reserved-fields.md`. In particular:
  no `stream_id`, no `assignments_hash`, no `schema_hash`, no
  `source_to_generic`, no `generic_to_destination`, no
  `type_mapping_assignments_hash`.
- `pipeline_id` is a **base** UUID — strip any `_v<n>` suffix the
  orchestrator might have accidentally passed.
- Every `endpoint_ref.connection_id` is a **versioned** ID — the same
  values appearing in `pipeline.connections`.
- Each `mapping.assignments[].value` has **exactly one** of
  `expression` or `constant`.
- `expression.op` is `"get"` (v1). No other op is supported.
- Database-only fields (`selected_columns`, `tie_breaker_fields`,
  `database_pagination`) are forbidden when the source `endpoint_ref.scope`
  is `connector` (API).
- API-only filter operators (`contains`, `starts_with`, `ends_with`)
  are forbidden when the source `endpoint_ref.scope` is `connection`
  (database).
- `scope: connection` is invalid for API endpoints (until snapshot
  hashing lands). Return a structured refusal if the orchestrator asks
  for that combination.
