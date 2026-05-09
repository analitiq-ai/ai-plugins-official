# Type maps

How to author connector-level `type_maps` mapping native types to Arrow
canonical types. The same `type_maps` block serves both database
connectors (mapping native database types) and API connectors (mapping
JSON Schema types/formats from endpoint response bodies).

## API connector convention

For API connectors, the `native` field of each rule is the **JSON
Schema `format` if present, otherwise the JSON Schema `type`**. The
validator walks every endpoint document under
`{alias}/definition/endpoints/`, collects `(type, format)` pairs from
each `response.schema` (recursively into properties / items / *Of
branches) and from each entry of `params` (which is an object keyed by
parameter name), and verifies the connector's `type_maps` rules cover
every native string. Coverage is enforced —
uncovered natives are validation **errors**, not warnings.

Common API natives:

| Native | Source | Typical canonical |
|---|---|---|
| `uuid` | `{"type":"string", "format":"uuid"}` | `String` |
| `date-time` | `{"type":"string", "format":"date-time"}` | `Timestamp` |
| `date` | `{"type":"string", "format":"date"}` | `Date32` |
| `email` / `uri` | `{"type":"string", "format":"…"}` | `String` |
| `string` | `{"type":"string"}` | `String` |
| `integer` | `{"type":"integer"}` | `Int64` |
| `int32` / `int64` | `{"type":"integer", "format":"…"}` | `Int32` / `Int64` |
| `number` | `{"type":"number"}` | `Float64` |
| `boolean` | `{"type":"boolean"}` | `Boolean` |

Object / array / null types are *not* collected as natives — the
walker recurses into them instead.

## Database connector convention

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
