# `endpoint_ref` shape

Source and every destination carry an `endpoint_ref`:

```jsonc
{
  "scope": "connector" | "connection",   // closed enum
  "connection_id": "<connection-uuid>",
  "endpoint_id": "<endpoint slug>"
}
```

## `scope`

| Value | Meaning |
|---|---|
| `connector` | Refers to a **public** endpoint baked into the connector document (typically API endpoints). Pinned by the connection's `connector_version` at runtime. |
| `connection` | Refers to a **private** connection-scoped endpoint (database snapshots produced by introspection). |

Under v1, `scope: connection` is only valid for **database** endpoints.
Connection-scoped API endpoints await an API endpoint snapshot-hashing
spec. The `endpoint-ref-shape` Layer 2 validator emits an error for any
other `scope` value; runtime additionally rejects `scope: connection`
on API endpoints.

## `connection_id`

The **`connection_id` UUID** of the connection the parent pipeline
selected for that side — source for `stream.source.endpoint_ref`,
destinations for `stream.destinations[].endpoint_ref`. The value must
match one of `pipeline.connections.source` or
`pipeline.connections.destinations[]`.

## `endpoint_id`

The stable endpoint identifier chosen from endpoint discovery. For API
endpoints, this matches a key from the connector's
`definition/endpoints/*.json`. For database endpoints, this matches the
`endpoint_id` on the introspection-authored endpoint document
(`^[a-z0-9][a-z0-9_-]*$`).

## Uniqueness

Destination `endpoint_ref` tuples `(scope, connection_id, endpoint_id)`
must be unique within a single stream. The `endpoint-ref-shape` validator
catches duplicates.

## Cross-document consistency

The `pipeline-stream-consistency` validator (run with `--bundle-root`)
asserts that:

- Every source `endpoint_ref.connection_id` equals
  `pipeline.connections.source`.
- Every destination `endpoint_ref.connection_id` is in
  `pipeline.connections.destinations`.
