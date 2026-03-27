---
name: mapping-spec
description: >
  Stream mapping specification for creating field-level mappings between source and destination
  endpoints. Contains assignment types, type matching rules, and three-way sync requirements.
  This skill should be loaded when creating or modifying field mappings between endpoints.
---

# Mapping Specification

Read the full mapping specification from `${CLAUDE_PLUGIN_ROOT}/skills/mapping-spec/spec-field-mapping.md` before creating any mapping.

## Three Coupled Sections

Every mapping has three sections that MUST stay in sync:

1. **assignments** — field-level mapping rules
2. **source_to_generic** — declares source fields and their generic types
3. **generic_to_destination** — declares destination fields, types, and nullability per connection ref

## Valid Generic Types

`string | integer | decimal | boolean | date | datetime | object | array`

## Assignment Types

### expr — extract from source:
```json
{
  "value": { "kind": "expr", "expr": { "op": "get", "path": ["fieldName"] } },
  "target": { "type": "VARCHAR(50)", "nullable": true, "path": ["dest_field"] }
}
```

### const — fixed value:
```json
{
  "value": { "kind": "const", "const": { "type": "integer", "value": 100 } },
  "target": { "type": "INTEGER", "nullable": false, "path": ["status"] }
}
```

## source_to_generic Example
```json
{
  "id": { "generic_type": "integer" },
  "status": { "generic_type": "string" },
  "created": { "generic_type": "datetime" }
}
```

## generic_to_destination Example
```json
{
  "conn_2": {
    "id": { "destination_type": "BIGINT", "nullable": false },
    "status": { "destination_type": "VARCHAR(50)", "nullable": true },
    "created": { "destination_type": "TIMESTAMP", "nullable": true }
  }
}
```

## Key Rules

- Target type in assignments uses the DESTINATION native type (e.g., `BIGINT`, `VARCHAR(50)`, `TIMESTAMP`)
- source_to_generic uses generic types (`integer`, `string`, `datetime`)
- generic_to_destination uses destination native types
- Nested source paths: `"path": ["originator", "name", "fullName"]`, dotted key in source_to_generic: `"originator.name.fullName"`
- Do NOT map parent objects when you need child scalars
- Do NOT include response-only fields (like `id` on POST/create endpoints) in assignments