# Assignment-level validation

Each `mapping.assignments[]` entry may carry an optional `validate`
block:

```jsonc
{
  "target": {"path": "email", "arrow_type": "Utf8", "nullable": false},
  "value": {"expression": {"op": "get", "path": "email"}},
  "validate": {
    "rules": [
      {"type": "required", "field": "email"},
      {"type": "pattern", "field": "email", "value": "^[^@]+@[^@]+$", "message": "Invalid email format."}
    ],
    "error_handling": {
      "strategy": "dlq",
      "max_retries": 0
    }
  }
}
```

## `rules[].type`

Closed enum:

| type | requires `value` | semantics |
|---|---|---|
| `required` | no | field must be present (any value) |
| `not_null` | no | field must be present and non-null |
| `min_length` | yes (integer) | string length ≥ value |
| `max_length` | yes (integer) | string length ≤ value |
| `pattern` | yes (regex string) | value matches the regex |
| `range` | yes (`{min,max}`) | numeric value within range |
| `in_list` | yes (array) | value is one of the listed values |

## `rules[].field`

Must match an `assignments[].target.path` in the same mapping. The
`mapping-shape` validator emits an error for `field` values that don't
resolve to a mapped output. This guards against silent typos.

## `error_handling`

Same shape as `pipeline.runtime.error_handling`:

```jsonc
{
  "strategy": "fail" | "dlq" | "skip",
  "max_retries": <0..5>,
  "retry_delay_seconds": <positive integer if max_retries > 0>
}
```

Per-assignment validation rules generally use `strategy: dlq` with
`max_retries: 0` — there's no point retrying a validation failure
against the same record.

## When to use

Use sparingly. Validation rules are useful for **defensive** checks
against malformed source data when the destination is strict (e.g.,
a column has a NOT NULL constraint that the source might violate).
For routine type coercion, rely on the registry's type-map machinery
rather than authoring `validate` blocks.
