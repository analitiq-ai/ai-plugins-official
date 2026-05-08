# Type maps (databases)

How to author connector-level `type_maps` mapping native database types
to Arrow canonical types.

## Shape

```json
{
  "type_maps": {
    "native_to_arrow": {
      "rules": [
        { "method": "exact",  "native": "INTEGER",                 "canonical": "Int32" },
        { "method": "exact",  "native": "BIGINT",                  "canonical": "Int64" },
        { "method": "regex",  "native": "^VARCHAR\\([0-9]+\\)$",   "canonical": "String" },
        { "method": "exact",  "native": "BOOLEAN",                 "canonical": "Boolean" }
      ]
    }
  }
}
```

## Methods

| Method | Match | Use |
|---|---|---|
| `exact` | Native string equals (case-insensitive). | The default — most database types. |
| `regex` | Native string matches a regular expression. | Parameterized types like `VARCHAR(n)`, `NUMERIC(p,s)`. |
| Agent reasoning | Authoring-time judgment baked into rules. | When official docs are ambiguous, the authoring agent picks the closest canonical type and notes the choice. |

## Canonical types

Arrow canonical types are PascalCase strings (e.g. `Int32`, `Int64`,
`Float64`, `String`, `Boolean`, `Binary`, `Date32`, `Time64`,
`Timestamp`, `Decimal128`, `List`, `Struct`, `Map`). The full vocabulary
is in `docs/schema-contracts/shared/canonical-types.json`.

## Rules

- Author exact rules where the database has a fixed type name.
- Use regex for parameterized types — but keep the regex anchored
  (`^...$`) so it doesn't accidentally match.
- Do NOT ship a wildcard fallback rule. If a native type isn't covered,
  let the runtime hard-error so the gap is visible.
- For OLTP databases (PostgreSQL, MySQL) you may include the full
  documented native vocabulary based on agent reasoning. For warehouses
  and NoSQL stores, restrict to the researched list — provider docs are
  authoritative.
- Do not invent canonical types. If you can't pick one from the
  vocabulary, mark the rule as `"canonical": "Binary"` only when the
  native type is genuinely opaque bytes.

## Connection-scoped overrides

Some native types only appear on certain deployments — PostGIS
`GEOMETRY`, pgvector `vector`, custom enum types. These are mapped in a
connection-scoped `type-map.json` produced during discovery, not in the
connector-level map. The runtime resolves connection-scoped first, then
connector-scoped, then hard-errors on no match.
