# `columns` block

A non-empty array. Each column declares:

```jsonc
{
  "name": "id",                              // required, minLength 1
  "native_type": "uuid",                     // required, minLength 1; "unknown" if undetectable
  "arrow_type": "Utf8",                      // required; fully-qualified Apache Arrow canonical type
  "nullable": false,                         // optional
  "default": null,                           // optional; any JSON value
  "comment": null,                           // optional; user or provider comment
  "ordinal_position": 1                      // optional integer >= 1
}
```

## `name`

Required. Verbatim from introspection.

## `native_type`

Required. Provider-native type label, e.g.:

| Dialect | examples |
|---|---|
| PostgreSQL | `uuid`, `text`, `integer`, `numeric(12,2)`, `timestamp with time zone`, `jsonb` |
| MySQL | `BIGINT UNSIGNED`, `VARCHAR(255)`, `DATETIME`, `JSON` |
| Snowflake | `NUMBER(38,0)`, `VARCHAR(16777216)`, `TIMESTAMP_TZ` |
| BigQuery | `STRING`, `INT64`, `STRUCT<…>`, `TIMESTAMP`, `BIGNUMERIC` |
| MongoDB | `BSON.ObjectId`, `BSON.Date`, `BSON.Document` |

Use `"unknown"` as a sentinel when the engine doesn't expose a type.

## `arrow_type`

Required. Fully-qualified Apache Arrow canonical type string. Base names
are PascalCase from `arrow/format/Schema.fbs`. Parameterized types must
carry their parameters — bare `Timestamp`, `Decimal128`, `Time64`,
`Duration`, `Interval`, `FixedSizeBinary`, `List`, `Struct`, `Map`, etc.
are rejected by the published schema.

### Three shapes

| Shape | Used for | Examples |
|---|---|---|
| Bare name | Scalar types with no parameters | `Utf8`, `Int64`, `Boolean`, `Date32`, `Binary` |
| Parens `( )` | Parameterized scalars (units, precision/scale, byte widths) | `Decimal128(38, 9)`, `Timestamp(MICROSECOND, UTC)`, `FixedSizeBinary(16)` |
| Angles `< >` | Nested types | `List<Int64>`, `Struct<id:Int64, name:Utf8>`, `Map<Utf8, Int64>` |

### Unit values

The literal Flatbuffers enum identifiers, uppercase:

- `TimeUnit`: `SECOND`, `MILLISECOND`, `MICROSECOND`, `NANOSECOND`
- `IntervalUnit`: `YEAR_MONTH`, `DAY_TIME`, `MONTH_DAY_NANO`

Not every type accepts every unit. The published regex restricts:

| Type | Allowed units |
|---|---|
| `Time32` | `SECOND`, `MILLISECOND` only |
| `Time64` | `MICROSECOND`, `NANOSECOND` only |
| `Timestamp`, `Duration` | all four `TimeUnit` values |
| `Interval` | `IntervalUnit` values only |

`Time32(MICROSECOND)` and `Time64(SECOND)` are rejected.

### `Timestamp` timezone

Optional second argument. Three valid forms:

- **Omit the slot** — naive timestamp, no implied zone: `Timestamp(MICROSECOND)`.
- **Literal `null`** — explicit naive marker: `Timestamp(MICROSECOND, null)`
  (distinct from omitting; some readers treat it as "zone is unknown
  rather than absent").
- **An actual zone** — IANA name (`UTC`, `Europe/Berlin`), `Etc/GMT±N`,
  or a fixed `±HH:MM` offset: `Timestamp(MICROSECOND, +05:30)`.

### Canonical examples

```
Utf8
Int64
Boolean
Date32
Decimal128(38, 9)
Decimal256(76, 0)
Timestamp(MICROSECOND)
Timestamp(MICROSECOND, UTC)
Timestamp(MILLISECOND, +05:30)
Time32(SECOND)
Time64(NANOSECOND)
Duration(MICROSECOND)
Interval(YEAR_MONTH)
FixedSizeBinary(16)
List<Int64>
LargeList<Utf8>
FixedSizeList<Int64>[8]
Struct<id:Int64, name:Utf8>
Map<Utf8, Int64>
Dictionary<Int32, Utf8>
```

### Mapping guidance

| Provider native | Typical fully-qualified `arrow_type` |
|---|---|
| `uuid`, `text`, `varchar(n)`, `char(n)` | `Utf8` |
| `smallint` / `integer` / `bigint` | `Int16` / `Int32` / `Int64` |
| `BIGINT UNSIGNED` (MySQL) | `UInt64` |
| `real` / `double precision` | `Float32` / `Float64` |
| `boolean` / `BOOL` | `Boolean` |
| `numeric(p,s)` / `DECIMAL(p,s)` | `Decimal128(p, s)` (use `Decimal256` when `p > 38`; max precision is 76) |
| `date` | `Date32` |
| `timestamp` / `DATETIME` (no zone) | `Timestamp(MICROSECOND)` |
| `timestamp with time zone` / `TIMESTAMP_TZ` / BigQuery `TIMESTAMP` | `Timestamp(MICROSECOND, UTC)` |
| BSON `Date` / JavaScript `Date` (ms epoch) | `Timestamp(MILLISECOND, UTC)` |
| `time` | `Time64(MICROSECOND)` |
| `bytea` / `BLOB` | `Binary` |
| arrays | `List<…>` |
| record / composite / STRUCT | `Struct<field:Type, …>` |

For schemaless or opaque container types (e.g. MongoDB `BSON.Document`,
PostgreSQL `jsonb` you do not introspect), prefer `Utf8` (JSON-as-text)
or `Binary` over guessing a `Struct<…>` field list.

### Inner grammar for `Struct<…>` / `Map<…>`

The published regex enforces only that the angle brackets are present and
non-empty (`Struct<.+>`, `Map<.+, .+>`); the inner grammar shown above
(`field:Type, …` for structs; `key, value` for maps) is the recommended
convention but is **not** regex-enforced. Stay consistent with the
canonical examples block so downstream consumers can parse the inner
shape unambiguously.

## `nullable`

Optional. `true` when the database reports the column as nullable, else
`false`. Omit when the dialect doesn't expose this (e.g., schemaless
engines).

## `default`

Optional. Any JSON value (the parsed default expression if reasonable,
or `null`). The runtime treats this as advisory — actual default
behavior is dialect-owned.

## `comment`

Optional. Provider-attached comment (PostgreSQL `COMMENT ON COLUMN`,
MySQL `COMMENT`, etc.). Forwarded verbatim. `null` when absent.

## `ordinal_position`

Optional integer ≥ 1. Used to canonicalize column order for hashing.
Omit for schemaless engines (MongoDB).

## Uniqueness

Per the `column-uniqueness` Layer 2 validator:

- `name` values are unique within the array.
- `ordinal_position` values are unique within the array (when present).
- Every `primary_keys[]` entry must reference an existing `name`.
