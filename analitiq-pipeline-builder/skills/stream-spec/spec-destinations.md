# `destinations` block

```jsonc
{
  "destinations": [
    {
      "endpoint_ref": { /* see spec-endpoint-refs.md */ },
      "write": {
        "mode": "insert" | "upsert" | "<api write mode>",
        "conflict_keys": [["id"]]                 // required when mode is `upsert` or an API mode that needs conflict targets
      },
      "execution": {                              // optional; per-destination override of pipeline.runtime.batching
        "batch_size": 1000,                       // range [1, 100000]
        "max_concurrent_batches": 3               // range [1, 100]
      }
    }
  ]
}
```

`destinations` is a non-empty array. Tuple `(scope, connection_id, alias)`
must be unique across entries.

## `write.mode`

| Destination kind | allowed values |
|---|---|
| database (scope=connection) | `insert`, `upsert` |
| API (scope=connector) | one of the endpoint's `operations.write` keys (e.g. `create`, `update`, `upsert`) — taken verbatim |

The orchestrator's `WriteModeMapper` (see
`../pipeline-builder/references/enum-mappers.md`) classifies the user's
intent to one of these.

## `write.conflict_keys`

Required when the mode resolves conflicts (database `upsert`; API
endpoints that document it). Shape:

```jsonc
[["id"], ["org_id", "external_id"]]
```

A non-empty array of non-empty key sets. Each inner array is one
candidate key. Multiple key sets indicate that any of them is sufficient
to identify a row.

Every key field must exist in the destination endpoint's schema.
Field-existence is enforced server-side at save time; the local
validator does **not** resolve field names against endpoint files.

## `execution` (per-destination override)

When present, **overrides** the pipeline-level
`runtime.batching.{batch_size,max_concurrent_batches}` for *this*
destination only. Use sparingly — pipeline defaults exist for a reason.

Typical use: a low-throughput destination next to a high-throughput one
in the same `destinations[]`.
