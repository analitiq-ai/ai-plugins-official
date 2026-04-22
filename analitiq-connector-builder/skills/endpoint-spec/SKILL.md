---
name: endpoint-spec
disable-model-invocation: true
description: >
  Endpoint specification knowledge for creating API endpoint definitions.
  Contains the JSON Schema format, filter definitions, pagination types, and replication
  filter mapping used by the Analitiq platform. This skill should be loaded when creating
  or modifying an API endpoint definition (endpoints/*.json). Database connectors do not
  have pre-defined endpoints — their schemas are discovered at runtime.
---

# Endpoint Specification

## Supporting Files

- [spec-api-endpoints.md](spec-api-endpoints.md) — full endpoint JSON schema, filter definitions, pagination types, replication filter mapping

Read the full endpoint specification from `${CLAUDE_PLUGIN_ROOT}/skills/endpoint-spec/spec-api-endpoints.md` before creating any endpoint.

## Quick Reference — API Endpoint

```json
{
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
        "created_at": { "type": "string", "format": "date-time", "description": "Creation timestamp" }
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

## Pagination Types

| Type | Key Params |
|------|------------|
| `offset` | `limit_param`, `offset_param` |
| `cursor` | `cursor_param`, `next_cursor_field` |
| `page` | `page_param`, `limit_param` |
| `link_header` | `uses_link_header: true` |

## Schema Field Types

- `string` (with optional `format`: `date-time`, `date`, `time`, `email`, `uri`)
- `integer`
- `number`
- `boolean`
- `object` (with nested `properties`)
- `array` (with `items`)
- Use `"nullable": true` for nullable fields
