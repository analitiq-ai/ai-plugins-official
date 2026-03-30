---
name: stream-spec
disable-model-invocation: true
description: >
  Stream specification for creating individual stream definitions within a pipeline.
  Contains the stream JSON format including source configuration, destination configuration,
  write modes, replication methods, and field mapping structure. This skill should be loaded
  when creating or modifying a stream definition.
---

# Stream Specification

## Supporting Files

- `${CLAUDE_PLUGIN_ROOT}/skills/mapping-spec/spec-field-mapping.md` — detailed field mapping rules, assignment types, three-way sync

Read the mapping specification from `${CLAUDE_PLUGIN_ROOT}/skills/mapping-spec/spec-field-mapping.md` before creating stream mappings.

## Stream JSON Structure

Each stream connects one source endpoint to one or more destination endpoints with field-level
mapping.

```json
{
  "version": 1,
  "source": {
    "connection_ref": "conn_1",
    "primary_key": ["id"],
    "replication": {
      "method": "full"
    }
  },
  "destinations": [
    {
      "connection_ref": "conn_2",
      "write": {
        "mode": "upsert",
        "conflict_keys": [["id"]]
      }
    }
  ],
  "mapping": {
    "assignments": [],
    "source_to_generic": {},
    "generic_to_destination": {},
    "assignments_hash": "",
    "type_mapping_assignments_hash": ""
  },
  "is_enabled": true,
  "status": "draft"
}
```

## Source Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connection_ref` | string | yes | Connection alias (e.g., `conn_1`) |
| `primary_key` | array of strings | no | Primary key column(s) for the source |
| `replication` | object | no | Replication configuration |
| `parameters` | object | no | Connector-specific parameters/filters |

### Replication Config

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | string | yes | `"full"` or `"incremental"` |
| `cursor_field` | array of strings | incremental only | Path to cursor field (required for incremental) |
| `safety_window_seconds` | integer | no | Safety window for late-arriving data |

## Destination Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connection_ref` | string | yes | Connection alias (e.g., `conn_2`) |
| `write` | object | no | Write mode configuration |
| `batching` | object | no | Batching overrides |

### Write Mode Config

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | yes | `"insert"` or `"upsert"` |
| `conflict_keys` | array of arrays | upsert only | Composite conflict resolution keys (required for upsert) |

When `mode` is `"upsert"`, `conflict_keys` is required and must contain at least one non-empty
key set. Each inner array is a set of field paths forming one unique constraint.

## Mapping

The `mapping` object contains:

| Field | Type | Description |
|-------|------|-------------|
| `assignments` | array | Ordered assignment rules (source field → target field) |
| `source_to_generic` | object | Source field paths mapped to `GenericTypeMapping` objects |
| `generic_to_destination` | object | Destination fields mapped to `DestinationTypeMapping` objects, keyed by connection_ref |
| `assignments_hash` | string | SHA256 hash of assignments (required when assignments is non-empty) |
| `type_mapping_assignments_hash` | string | Hash tracking when type mappings were generated |

### Type Mapping Shapes

**`source_to_generic`** — each value is a `GenericTypeMapping` object, not a plain string:

```json
"source_to_generic": {
  "id": { "generic_type": "integer" },
  "name": { "generic_type": "string" },
  "amount": { "generic_type": "decimal" },
  "created_at": { "generic_type": "datetime" }
}
```

**`generic_to_destination`** — keyed by connection_ref, each value maps field paths to
`DestinationTypeMapping` objects:

```json
"generic_to_destination": {
  "conn_2": {
    "id": { "destination_type": "BIGINT", "nullable": false },
    "name": { "destination_type": "VARCHAR(255)", "nullable": false },
    "amount": { "destination_type": "NUMERIC(12,2)", "nullable": true },
    "created_at": { "destination_type": "TIMESTAMP WITH TIME ZONE", "nullable": true }
  }
}
```

See the `mapping-spec` skill for the full assignment structure, type matching rules, and
three-way consistency requirements.

## Valid Enums

**Replication methods:** `full`, `incremental`

**Write modes:** `insert`, `upsert`

**Stream statuses:** `draft`, `active`, `paused`, `error`

**Error actions:** `retry`, `dlq`, `retry_with_backoff`, `skip`, `fail`

**Data types:** `string`, `integer`, `decimal`, `boolean`, `date`, `datetime`, `timestamp`,
`object`, `array`, `json`

## Key Rules

- Each stream-builder creates exactly one stream file
- `conflict_keys` is required when write mode is `upsert`
- `cursor_field` is required when replication method is `incremental`
- `assignments_hash` is required when assignments is non-empty
- Three-way consistency must hold between `assignments`, `source_to_generic`, and `generic_to_destination`

## Output

Save each stream as an individual JSON file:
```
pipelines/{pipeline-name}/streams/{stream-name}.json
```

Use a descriptive filename derived from the source endpoint. For example:
- Source `/v1/transfers` → `transfers.json`
- Source `public/users` → `public-users.json`
