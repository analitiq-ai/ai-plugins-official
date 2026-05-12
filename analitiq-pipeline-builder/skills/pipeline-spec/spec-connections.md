# `connections` block

```jsonc
{
  "connections": {
    "source": "<connection-alias>",          // required
    "destinations": ["<connection-alias>", …] // required, non-empty, no duplicates
  }
}
```

## Connection alias format

`^[a-z0-9][a-z0-9_-]*$`, e.g. `"wise"`, `"postgresql_prod"`,
`"snowflake_warehouse"`. The alias matches the directory name under
`connections/{alias}/` and is the same value the engine resolves at
runtime. See `../pipeline-builder/references/identity-and-versioning.md`.

## Rules

- `source` is a single alias, not an array.
- `destinations` is a non-empty array, with at least one alias.
- No duplicates in `destinations`.
- A destination alias may equal the source alias — that's a legitimate
  self-loop (e.g., copying data within a single database between
  schemas).
- Every alias must resolve to a connection owned by the same org. The
  plugin does not enforce ownership; the registry does at save time.

## What is NOT in this block

- Connection bodies. Those live in `connections/{alias}/connection.json`.
- Connection credentials. Those live in `connections/{alias}/.secrets/`.
- The connector reference. The pipeline references **connections**, not
  connectors. The connection points back at its connector via
  `connector_alias`.