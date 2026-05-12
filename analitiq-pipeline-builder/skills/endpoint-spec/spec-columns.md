# `columns` block

A non-empty array. Each column declares:

```jsonc
{
  "name": "id",                              // required, minLength 1
  "native_type": "uuid",                     // required, minLength 1; "unknown" if undetectable
  "arrow_type": "Utf8",                      // optional; Apache Arrow PascalCase
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

## `arrow_type` (optional)

PascalCase Apache Arrow canonical type. Pattern: `^[A-Z][A-Za-z0-9]*$`.

| arrow_type | typical mapping |
|---|---|
| `Utf8` | strings, UUIDs, JSON-as-text |
| `Int32`, `Int64` | small / big integers |
| `Float32`, `Float64` | floats |
| `Decimal128` | NUMERIC / DECIMAL |
| `Boolean` | booleans |
| `Date32` | DATE |
| `Timestamp` | TIMESTAMP / DATETIME |
| `Binary` | BYTEA, BLOB |
| `Struct` | composite types |
| `List` | arrays |

Omit `arrow_type` when the mapping is ambiguous — the registry / runtime
resolves it from `native_type` against the shared type map.

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
