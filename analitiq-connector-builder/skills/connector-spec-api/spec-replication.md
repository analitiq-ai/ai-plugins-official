# Replication (incremental sync)

Authoring `operations.read.replication` for endpoints that support
incremental sync.

## Cursor mappings

`replication.cursor_mappings` declares which response fields should be
captured as the per-record cursor and how to filter the next sync run by
that cursor.

```json
{
  "replication": {
    "cursor_mappings": [
      {
        "name": "updated_at",
        "value": { "ref": "record.updated_at" },
        "filter_param": "updated_since",
        "filter_operator": "gte"
      }
    ]
  }
}
```

- `name` is the cursor name (state key the runtime persists).
- `value` is a `ref` into each record that yields the cursor value.
- `filter_param` is the operation `param` name used to filter by the cursor.
- `filter_operator` is the operator from the closed list defined in
  `docs/schema-contracts/shared/filter-operators.md` (`eq`, `neq`, `gt`,
  `gte`, `lt`, `lte`, `in`, `exists`, `missing`).

## Supported methods

If an endpoint supports both full and incremental sync, declare which is
default and which the user can opt into:

```json
{
  "replication": {
    "supported_methods": ["incremental", "full"],
    "default_method": "incremental"
  }
}
```

## When to omit

Omit `replication` entirely when:

- The resource has no cursorable field (no `updated_at`, no monotonic id).
- The endpoint is a small static lookup (countries, currencies).
- The provider doesn't expose a filter param for the cursor field.

## Common pitfalls

- Don't fabricate a cursor field. If `updated_at` is response-side only
  (no filter param), there's no incremental sync to declare.
- The cursor value expression must resolve per-record, not once per
  page — use `ref: "record.X"`, not `ref: "response.body.records[-1].X"`.
- Don't add a `type-map` field to `cursor_mappings`; canonical types are
  resolved through the connector's or connection's `type_maps`.
