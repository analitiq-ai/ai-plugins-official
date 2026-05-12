# `mapping` block

`mapping` is **optional**. Omit it (or pass `null`) for the default
pass-through mapping: every source field is mapped 1:1 to a destination
field with the same name and the type the registry derives from the
shared canonical-type vocabulary.

When you do author it, the shape is **assignments-only**. The registry
computes `assignments_hash`, `source_to_generic`,
`generic_to_destination`, and `type_mapping_assignments_hash`. **The
plugin must not author those fields.**

```jsonc
{
  "mapping": {
    "assignments": [
      {
        "target": {
          "path": "id",                  // required; destination field reference
          "arrow_type": "Utf8",          // required; fully-qualified Arrow canonical type
          "native_type": "uuid",         // optional; destination-native type override
          "nullable": false              // default true
        },
        "value": {                       // exactly one of expression / constant
          "expression": {"op": "get", "path": "id"}
        }
      },
      {
        "target": {"path": "tenant_id", "arrow_type": "Utf8", "nullable": false},
        "value": {
          "constant": {"arrow_type": "Utf8", "value": "acme-corp"}
        }
      }
    ]
  }
}
```

## `assignments[].value`

Exactly one of:

- `expression` — a v1 `get` op: `{"op": "get", "path": "<source field>"}`.
  No other ops are supported yet. Future ops are reserved but not
  defined.
- `constant` — `{"arrow_type": "<fully-qualified Arrow type>", "value": <JSON value>}`.

The `mapping-shape` Layer 2 validator emits an error when both or
neither is present, and when `expression.op != "get"`.

## `assignments[].target.path`

Must be unique within `assignments`. The `mapping-shape` validator
catches duplicates.

Cross-document: each `target.path` must exist in the resolved
destination endpoint schema. Endpoint resolution is server-side at
save time; the local validator does **not** check this.

## `arrow_type` vocabulary

Both `target.arrow_type` and `constant.arrow_type` are **required** and
must be **fully-qualified** Apache Arrow canonical type strings. The
published `stream/latest.json` schema rejects bare parameterized forms
(`Timestamp`, `Decimal128`, `Time64`, `Duration`, `Interval`,
`FixedSizeBinary`, `List`, `Struct`, `Map`, …). See
[`endpoint-spec/spec-columns.md`](../endpoint-spec/spec-columns.md)
for the canonical reference: the three shapes (bare / `( )` / `< >`),
unit identifiers, and timezone forms apply identically here.

Common forms:

| arrow_type | description |
|---|---|
| `Utf8` | UTF-8 string |
| `Int32`, `Int64`, `UInt64` | signed / unsigned integers |
| `Float32`, `Float64` | floating point |
| `Boolean` | boolean |
| `Decimal128(p, s)` | fixed precision; carry precision and scale from `native_type` (e.g. `NUMERIC(12,2)` → `Decimal128(12, 2)`) |
| `Date32` | calendar date |
| `Timestamp(MICROSECOND)` / `Timestamp(MICROSECOND, UTC)` | timestamp without / with timezone |
| `Time64(MICROSECOND)` | time-of-day |
| `Binary` | raw bytes |
| `List<…>`, `Struct<…>`, `Map<…, …>` | composite |

The full vocabulary is owned by
`analitiq-infra/docs/schema-contracts/shared/canonical-types.json`.
Stick to what the destination endpoint's `columns[]` declares — if the
destination column is `Decimal128(12, 2)`, the assignment's
`target.arrow_type` must match exactly.
