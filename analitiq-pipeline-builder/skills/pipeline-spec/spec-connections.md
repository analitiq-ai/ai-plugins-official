# `connections` block

```jsonc
{
  "connections": {
    "source": "<versioned-connection-id>",          // required
    "destinations": ["<versioned-connection-id>", …] // required, non-empty, no duplicates
  }
}
```

## Versioned connection ID format

`<uuid>_v<positive integer>`, e.g.
`00000000-0000-4000-8000-000000000001_v1`.

See `../pipeline-builder/references/identity-and-versioning.md` for how
the orchestrator mints placeholder IDs deterministically from the
connection alias.

## Rules

- `source` is a single ID, not an array.
- `destinations` is a non-empty array, with at least one ID.
- No duplicates in `destinations`.
- A destination ID may equal the source ID — that's a legitimate self-
  loop (e.g., copying data within a single database between schemas).
- Every ID must resolve to a connection owned by the same org. The
  plugin does not enforce ownership; the registry does at save time.

## What is NOT in this block

- Connection bodies. Those live in `connections/{alias}/connection.json`.
- Connection credentials. Those live in `connections/{alias}/.secrets/`.
- The connector reference. The pipeline references **connections**, not
  connectors. The connection points back at its connector via
  `connector_alias`.
