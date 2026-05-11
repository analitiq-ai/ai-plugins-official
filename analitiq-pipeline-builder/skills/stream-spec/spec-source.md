# `source` block

```jsonc
{
  "source": {
    "endpoint_ref": { /* see spec-endpoint-refs.md */ },
    "selected_columns": ["id", "amount", "updated_at"],  // optional, database only
    "filters": [                                          // optional
      {"field": "status", "operator": "eq", "value": "paid"}
    ],
    "replication": {                                      // optional, defaults to full_refresh
      "method": "incremental",                            // "full_refresh" | "incremental"
      "cursor_field": "updated_at",                       // required if method == incremental
      "safety_window_seconds": 300,                       // optional, non-negative
      "tie_breaker_fields": ["id"]                        // optional, database only
    },
    "database_pagination": {                              // optional, database only
      "type": "offset",                                   // "offset" | "keyset"
      "page_size": 1000,                                  // optional
      "order_by_field": "id"                              // required if type == keyset
    },
    "primary_keys": ["id"]                                // optional; identity hint for sources without PK metadata
  }
}
```

## `selected_columns` (database only)

A field projection. Omit for "all columns from the endpoint schema."
Every entry must exist in the resolved endpoint's `columns[]`. The
`pipeline-stream-consistency` validator verifies this when the source
endpoint can be resolved.

## `filters`

Stream-owned read predicates. The operator vocabulary depends on the
endpoint kind:

- Database endpoints (`scope: connection`): see `spec-filter-operators.md` § database operators.
- API endpoints (`scope: connector`): operators must be in the
  endpoint's `operations.read.params.<name>.allowed_operators`.

Unary operators (`is_null`, `is_not_null`) must **omit** `value`.
Non-unary operators must **include** `value`.

## `replication`

Default when omitted: `{method: "full_refresh"}` (the source must
support full refresh; the connector declares this).

- `method`: `full_refresh` or `incremental`.
- `cursor_field`: required for `incremental`; the source field used as
  the watermark.
- `safety_window_seconds`: non-negative integer of seconds for late-
  arrival overlap on incremental syncs.
- `tie_breaker_fields`: ordered field set for deterministic ordering
  when cursor values tie. **Database sources only.** API sources
  reject this field.

## `database_pagination` (database only)

| `type` | extra fields |
|---|---|
| `offset` | `page_size` (default applies if omitted, taken from `pipeline.runtime.batching.batch_size`) |
| `keyset` | `order_by_field` (required), `page_size` (optional) |

## `primary_keys`

Optional identity hint. Use only when the endpoint's own primary-key
metadata is unavailable (typical for API endpoints). When the endpoint
declares primary keys, omit this — declaring conflicting keys is an
error.
