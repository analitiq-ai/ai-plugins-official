---
name: endpoint-spec
description: >
  Endpoint specification knowledge for creating API and database endpoint definitions.
  Contains the JSON Schema format, filter definitions, pagination types, and replication
  filter mapping used by the Analitiq platform. This skill should be loaded when creating
  or modifying an endpoint definition (endpoints/*.json).
---

# Endpoint Specification

Read the full endpoint specification from `${CLAUDE_PLUGIN_ROOT}/skills/endpoint-spec/spec-api-endpoints.md` before creating any endpoint.

## Quick Reference — API Endpoint

```json
{
  "connector_id": "uuid",
  "endpoint_id": "uuid_v1",
  "endpoint": "/v1/resource",
  "method": "GET",
  "version": 1,
  "endpoint_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Resource List",
    "description": "Returns an array of resource objects",
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "id": { "type": "integer", "description": "Resource ID" },
        "name": { "type": "string", "description": "Resource name" },
        "created_at": { "type": "string", "format": "datetime", "description": "Creation timestamp" }
      }
    }
  },
  "filters": {
    "since": {
      "description": "Filter by creation date",
      "type": "string",
      "operators": ["gte"],
      "required": false,
      "example": "2024-01-01T00:00:00Z"
    }
  },
  "pagination": {
    "type": "offset",
    "params": {
      "limit_param": "limit",
      "offset_param": "offset",
      "max_limit": null,
      "cursor_param": null,
      "next_cursor_field": null,
      "page_param": null,
      "uses_link_header": false,
      "time_window_params": { "start_param": null, "end_param": null }
    }
  },
  "replication_filter_mapping": {
    "created_at": "since"
  }
}
```

## Quick Reference — Database Endpoint

```json
{
  "connector_id": "uuid",
  "endpoint_id": "uuid_v1",
  "endpoint": "public/table_name",
  "method": "DATABASE",
  "version": 1,
  "endpoint_schema": {
    "columns": [
      { "name": "id", "type": "BIGINT", "nullable": false, "default": null, "autoincrement": false, "comment": null },
      { "name": "name", "type": "VARCHAR(255)", "nullable": true, "default": null },
      { "name": "_synced_at", "type": "TIMESTAMP", "nullable": true, "default": "now()" }
    ],
    "primary_keys": ["id"]
  }
}
```

## Pagination Types

| Type | Key Params |
|------|------------|
| `offset` | `limit_param`, `offset_param` |
| `cursor` | `cursor_param`, `next_cursor_field` |
| `page` | `page_param`, `limit_param` |
| `link_header` | `uses_link_header: true` |

## Schema Field Types

- `string` (with optional `format`: `datetime`, `date`, `time`, `email`, `uri`)
- `integer`
- `number`
- `boolean`
- `object` (with nested `properties`)
- `array` (with `items`)
- Use `"nullable": true` for nullable fields