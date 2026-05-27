# Type maps

How to author the standalone `type-map.json` that ships alongside every
connector. The type map maps provider-native type labels to Apache Arrow
canonical types. The same file shape serves both database connectors
(mapping native database types like `bigint`, `numeric(10,2)`) and API
connectors (mapping the JSON Schema `format`/`type` strings used as
endpoint-field natives).

## On-disk location

`type-map.json` is a **standalone file** at:

```
{connector_id}/definition/type-map.json
```

It validates against `https://schemas.analitiq.ai/type-map/latest.json`.
It is never embedded inside `connector.json` or any endpoint document.

A `type-map.json` is **required** for every connector (API and DB) and
must be **non-empty**. An empty array is rejected by the schema.

## File shape

The file is a top-level JSON array of rule objects. Order is significant:
**first match wins** during resolution. Each rule object has exactly
three required keys and no others:

| Key | Type | Description |
|---|---|---|
| `match` | `"exact"` or `"regex"` | How `native` is compared against the runtime native-type label. |
| `native` | string | The literal label (for `exact`) or an ECMA-262 regular expression (for `regex`). The validator and runtime both match with full-string semantics (Python `re.fullmatch`), so leading `^` and trailing `$` are harmless but redundant — keep them for readability when the pattern would otherwise look ambiguous. |
| `canonical` | string | The target Arrow canonical type. For `exact` rules, a literal canonical (e.g. `Int64`, `Decimal128(38, 0)`). For `regex` rules, either a literal canonical OR a templated canonical with `${name}` placeholders in parameter positions (e.g. `Decimal128(${precision}, ${scale})`). |

## `${name}` substitution in regex rules

When a `regex` rule's `canonical` carries `${name}` placeholders, every
placeholder must be backed by a matching **named capture group** in
`native`. The validator uses ECMA-262 syntax for capture groups —
`(?<name>…)` — which is translated to Python's `(?P<name>…)` under the
hood at validation time. Authors write the ECMA-262 form.

Placeholders are only legal in **parameter positions** of parameterized
canonical types:

- `Decimal128(${precision}, ${scale})`
- `Timestamp(${unit}, ${tz})`
- `FixedSizeBinary(${n})`

A free-form string with a placeholder outside a parameter position
(`not an arrow type ${x}`) is rejected. Templated canonicals are only
legal on `regex` rules; `exact` rules must emit a fully-resolved literal.

## Schemaless / JSON-shaped natives → `Json`

Schemaless container natives map to the `Json` canonical:

| Provider | Native | Canonical |
|---|---|---|
| Postgres | `jsonb`, `json` | `Json` |
| MySQL | `json` | `Json` |
| Snowflake | `VARIANT`, `OBJECT`, `ARRAY` | `Json` |
| MongoDB | `array`, `object` | `Json` |

The endpoint-only shape markers `Object` and `List` (which require
sibling `properties` / `items` to declare the inner shape) **never**
appear as a type-map `canonical`. The endpoint walker accepts a field
typed `Object` or `List` as a valid narrowing of a `Json` type-map rule;
the validator does not treat that as a mismatch.

## API coverage

For API connectors, the validator walks every endpoint file under
`{connector_id}/definition/endpoints/`, collects every `(native_type,
arrow_type)` pair from typed fields, and asserts each one resolves
through `type-map.json`. Resolution renders the matched rule's
`canonical` (substituting any `${name}` captures from the regex match)
and compares the result to the endpoint field's `arrow_type`. A pair
that does not resolve is a validation error.

`Object` / `List` endpoint markers are accepted narrowings of `Json` —
an endpoint field with `arrow_type: "Object"` paired with a native that
maps to `Json` is **not** a mismatch.

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
| `object` (schemaless) | `{"type":"object"}` with no `properties` | `Json` |
| `array` (schemaless) | `{"type":"array"}` with no `items` | `Json` |

## Database coverage

For database connectors, ship the documented provider native vocabulary.

- For OLTP databases (PostgreSQL, MySQL), include the full documented
  native vocabulary.
- For warehouses and document stores (Snowflake, MongoDB), restrict to
  the researched, documented list — provider docs are authoritative.
- Do NOT ship a wildcard fallback rule. If a native type isn't covered,
  let the runtime hard-error so the gap is visible.
- Anchors (`^…$`) are redundant since the matcher uses full-string
  semantics, but they're often kept for readability.
- Use `Utf8` (not `String`) for Arrow's UTF-8 string type — `String` is
  not a member of the published Arrow vocabulary.

## Canonical types

Arrow canonical types are fully-qualified PascalCase strings from the
shared Arrow vocabulary — bare names where the type has no parameters
(`Int32`, `Int64`, `Float64`, `Utf8`, `Boolean`, `Binary`, `Date32`),
parens for parameterized scalars (`Decimal128(p, s)`,
`Timestamp(MICROSECOND, UTC)`, `Time64(MICROSECOND)`,
`FixedSizeBinary(16)`), and angle brackets for nested types
(`List<Int64>`, `Struct<id:Int64, name:Utf8>`, `Map<Utf8, Int64>`).

The full vocabulary lives in
`docs/schema-contracts/shared/canonical-types.json`.

For parameterized canonicals whose database native carries an implicit
default, encode the default explicitly:

- Snowflake `TIMESTAMP_NTZ` → `Timestamp(NANOSECOND)` (precision 9).
- Snowflake `NUMBER` → `Decimal128(38, 0)`.
- MongoDB `date` → `Timestamp(MILLISECOND, UTC)` (ms epoch UTC).
- MongoDB `decimal` → `Decimal128(34, 0)` (IEEE 754 decimal128).

Do NOT emit a bare parameterized name from an `exact` rule
(`{"match": "exact", "native": "TIMESTAMP_NTZ", "canonical": "Timestamp"}`
is wrong — `Timestamp` requires a unit).

## Worked example: Postgres

The Postgres example demonstrates the split-rule pattern for `numeric`
(an `exact` default plus a `regex` with named captures) and the
literal-form pattern for parameterized time/timestamp types.

```json
[
  { "match": "exact", "native": "smallint",          "canonical": "Int16" },
  { "match": "exact", "native": "integer",           "canonical": "Int32" },
  { "match": "exact", "native": "bigint",            "canonical": "Int64" },
  { "match": "exact", "native": "boolean",           "canonical": "Boolean" },
  { "match": "exact", "native": "text",              "canonical": "Utf8" },
  { "match": "regex", "native": "^character varying(\\([0-9]+\\))?$", "canonical": "Utf8" },
  { "match": "exact", "native": "uuid",              "canonical": "Utf8" },
  { "match": "exact", "native": "date",              "canonical": "Date32" },
  { "match": "regex", "native": "^time(\\([0-9]+\\))?( without time zone)?$",      "canonical": "Time64(MICROSECOND)" },
  { "match": "regex", "native": "^timestamp(\\([0-9]+\\))?( without time zone)?$", "canonical": "Timestamp(MICROSECOND)" },
  { "match": "regex", "native": "^timestamp(\\([0-9]+\\))? with time zone$",       "canonical": "Timestamp(MICROSECOND, UTC)" },
  { "match": "regex", "native": "^numeric\\((?<precision>[0-9]+),\\s*(?<scale>[0-9]+)\\)$", "canonical": "Decimal128(${precision}, ${scale})" },
  { "match": "exact", "native": "numeric",           "canonical": "Decimal128(38, 0)" },
  { "match": "exact", "native": "bytea",             "canonical": "Binary" },
  { "match": "exact", "native": "jsonb",             "canonical": "Json" },
  { "match": "exact", "native": "json",              "canonical": "Json" }
]
```

The `numeric` split — regex (with `(?<precision>…)` / `(?<scale>…)`
named captures rendering into `Decimal128(${precision}, ${scale})`)
above an `exact` fallback for unqualified `numeric` — is the canonical
pattern for parameterized DB types. First-match-wins means the more
specific regex must come **before** the bare-name fallback.

## Out of scope

Connection-scoped type maps are out of scope for this plugin; see
`shared/type-maps.md` for runtime resolution rules.
