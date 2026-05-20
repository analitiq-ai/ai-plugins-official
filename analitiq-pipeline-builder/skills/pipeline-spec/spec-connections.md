# `connections` block

```jsonc
{
  "connections": {
    "source": "<connection-uuid>",          // required
    "destinations": ["<connection-uuid>", …] // required, non-empty, no duplicates
  }
}
```

## Connection reference format

A connection reference is the `connection_id` UUID of the corresponding
connection document. The schema accepts any non-empty string here, but
the engine resolves references at runtime against authored `connection_id`
values, so the plugin must emit the UUID, not the directory slug.

Directory layout stays human-readable
(`connections/<connection-slug>/connection.json`); the slug is only used
for file organization, not for cross-document identity. See
`../pipeline-builder/references/identity-and-versioning.md`.

## Rules

- `source` is a single UUID string, not an array.
- `destinations` is a non-empty array, with at least one UUID.
- No duplicates in `destinations`.
- A destination UUID may equal the source UUID — that's a legitimate
  self-loop (e.g., copying data within a single database between
  schemas).
- Every UUID must resolve to a connection owned by the same org. The
  plugin does not enforce ownership; the registry does at save time.

## What is NOT in this block

- Connection bodies. Those live in
  `connections/<connection-slug>/connection.json`.
- Connection credentials. Those live in
  `connections/<connection-slug>/.secrets/`.
- The connector reference. The pipeline references **connections**, not
  connectors. The connection points back at its connector via
  `connector_id`.
