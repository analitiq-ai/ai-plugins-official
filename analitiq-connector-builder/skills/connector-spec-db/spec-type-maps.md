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
| `uuid` | `{"type":"string", "format":"uuid"}` | `Utf8` |
| `date-time` | `{"type":"string", "format":"date-time"}` | `Timestamp(MICROSECOND, UTC)` |
| `date` | `{"type":"string", "format":"date"}` | `Date32` |
| `email` / `uri` | `{"type":"string", "format":"…"}` | `Utf8` |
| `string` | `{"type":"string"}` | `Utf8` |
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
        { "method": "regex",  "native": "^VARCHAR\\([0-9]+\\)$",   "canonical": "Utf8" },
        { "method": "regex",  "native": "^NUMERIC\\([0-9]+,[0-9]+\\)$", "canonical": "Decimal128" },
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

Arrow canonical types are fully-qualified PascalCase strings from the
shared Arrow vocabulary — bare names where the type has no parameters
(`Int32`, `Int64`, `Float64`, `Utf8`, `Boolean`, `Binary`, `Date32`),
parens for parameterized scalars (`Decimal128(p, s)`,
`Timestamp(MICROSECOND, UTC)`, `Time64(MICROSECOND)`,
`FixedSizeBinary(16)`), and angle brackets for nested types
(`List<Int64>`, `Struct<id:Int64, name:Utf8>`, `Map<Utf8, Int64>`). See
`analitiq-pipeline-builder/skills/endpoint-spec/spec-columns.md` for the
authoritative reference — endpoint columns produced from this map must
match the same vocabulary.

The full vocabulary is in
`docs/schema-contracts/shared/canonical-types.json`.

### `canonical` value forms by `method`

| Rule `method` | Required `canonical` form |
|---|---|
| `exact` | The fully-qualified type literal. For non-parameterized canonical types (`Utf8`, `Boolean`, `Int64`, `Date32`, `Binary`, …), the bare name. For parameterized canonical types whose database native carries an implicit default (Snowflake `TIMESTAMP_NTZ` defaults to precision 9 → `Timestamp(NANOSECOND)`; Snowflake `NUMBER` defaults to `(38, 0)` → `Decimal128(38, 0)`; MongoDB `date` is ms epoch UTC → `Timestamp(MILLISECOND, UTC)`; MongoDB `decimal` is IEEE 754 decimal128 with 34 significant digits → `Decimal128(34, 0)`), encode the default explicitly. |
| `regex` matching a non-parameterized native (e.g. `^text$`) | A fully-qualified literal (e.g. `Utf8`). |
| `regex` matching a parameterized native (e.g. `^NUMERIC\([0-9]+,[0-9]+\)$`, `^timestamp(\([0-9]+\))?( with time zone)?$`) | The **base PascalCase name** (e.g. `Decimal128`, `Timestamp`). The runtime carries the parameter substrings from the captured native into the canonical at discovery time. |

The regex split is a temporary contract: `type_maps` does not yet
support capture-group templating, so the engine derives parameters from
`native_type` at discovery. Until that lands, regex rules for
parameterized natives must emit the base name and let the runtime
parameterize. Do **not** write `"canonical": "Decimal128(p, s)"` —
literal `p` / `s` will not be substituted.

Do **not** emit a bare parameterized name from an `exact` rule
(`{"method": "exact", "native": "TIMESTAMP_NTZ", "canonical": "Timestamp"}`
is wrong — `Timestamp` requires a unit). Pick the database's documented
default precision/scale and encode it literally.

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
- Use `Utf8` (not `String`) for Arrow's UTF-8 string type — `String` is
  not a member of the published Arrow vocabulary.

## Connection-scoped overrides

Some native types only appear on certain deployments — PostGIS
`GEOMETRY`, pgvector `vector`, custom enum types. These are mapped in a
connection-scoped `type-map.json` produced during discovery, not in the
connector-level map. The runtime resolves connection-scoped first, then
connector-scoped, then hard-errors on no match.
