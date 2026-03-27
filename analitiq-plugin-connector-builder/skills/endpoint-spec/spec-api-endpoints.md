# API Connector Endpoints

This document covers how connector endpoints are defined for API connectors (`connector_type: "api"`). For general connector structure see [spec-common-attributes.md](../connector-spec/spec-common-attributes.md). For database/file connector endpoints, use `method: "DATABASE"` and a column-based `endpoint_schema` — see the DB endpoint section below.

Each API connector has one or more **endpoints** — individual API paths that the pipeline runner can extract data from. Endpoints are saved as JSON files under the connector's `definition/endpoints/` directory.

## API Endpoint Record

Every API endpoint record has these attributes:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `connector_id` | string (UUID) | yes | Connector this endpoint belongs to |
| `endpoint_id` | string (UUID) | yes | Unique endpoint identifier (auto-generated on create) |
| `endpoint` | string | yes | API path relative to `base_url` (e.g. `/v1/transfers`) |
| `method` | string | yes | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS` |
| `version` | integer | yes | Record version (starts at 1, increments on schema changes) |
| `endpoint_schema` | object | yes | JSON Schema describing the response payload |
| `filters` | object | no | Query parameter filter definitions |
| `pagination` | object | no | Pagination configuration |
| `replication_filter_mapping` | object | no | Maps response fields to filter params for incremental sync |
| `_content_hash` | string | auto | SHA256 hash of `endpoint_schema` for change detection |

## `endpoint_schema`

The schema follows [JSON Schema draft 2020-12](https://json-schema.org/draft/2020-12/schema) and describes the structure of the API response payload.

### Flat object response

When the API returns a single object per record:

```json
{
  "endpoint_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CheckAccountTransaction Response",
    "description": "Response for creating a new check account transaction",
    "type": "object",
    "properties": {
      "id": { "type": "string", "description": "Transaction ID" },
      "amount": { "type": "string", "description": "Amount of the transaction" },
      "status": {
        "type": "string",
        "description": "Transaction status",
        "enum": ["100", "200", "300", "350", "400"]
      },
      "valueDate": {
        "type": "string",
        "format": "date-time",
        "description": "Date the transaction was imported"
      }
    },
    "required": ["id", "amount", "status"]
  }
}
```

### Array response

When the API returns a list of records, the schema uses `type: "array"` with `items`:

```json
{
  "endpoint_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Transfers List",
    "description": "Returns an array of transfer objects",
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "id": { "type": "integer", "description": "Transfer ID" },
        "status": { "type": "string", "description": "Transfer status" },
        "rate": { "type": "number", "description": "Exchange rate value" },
        "created": { "type": "string", "format": "date-time", "description": "When transfer was created" }
      }
    }
  }
}
```

### Nested objects

Nested objects use `type: "object"` with their own `properties`:

```json
{
  "checkAccount": {
    "type": "object",
    "description": "The check account this transaction belongs to",
    "properties": {
      "objectName": { "type": "string" },
      "id": { "type": "string" }
    },
    "required": ["id", "objectName"]
  }
}
```

### Arrays and the dot-path convention

For arrays in the endpoint schema, the backend uses a **dot-path** convention to represent the path as a list: `["addresses", "street"]`. There is no handling for `schema.items?.properties` — array fields are all pushed as type `array` without expanding nested properties.

Example — a field containing an array of strings:

```json
{
  "middleNames": {
    "type": "array",
    "description": "Middle name(s)",
    "items": { "type": "string" }
  }
}
```

The backend represents this field's path as `["originator", "name", "middleNames"]`. The nested properties inside `items` (if any) are **not** expanded — the entire field is treated as a single `array` column.

### Nullable fields

Use `"nullable": true` alongside the type:

```json
{
  "payeePayerName": {
    "type": "string",
    "nullable": true,
    "description": "Name of the other party"
  }
}
```

## `filters`

Defines the query parameters the endpoint supports for filtering results. Each key is the parameter name as it appears in the API query string.

```json
{
  "filters": {
    "createdDateStart": {
      "description": "Starting date to filter transfers",
      "type": "string",
      "operators": ["gte"],
      "required": false,
      "example": "2018-12-15T00:00:00.000Z"
    },
    "status": {
      "description": "Comma separated status codes",
      "type": "string",
      "operators": ["eq", "in"],
      "required": false
    },
    "profile": {
      "description": "User profile ID",
      "type": "integer",
      "operators": ["eq"],
      "required": false
    }
  }
}
```

### Filter definition fields

| Field | Type | Description |
|-------|------|-------------|
| `description` | string | Human-readable description |
| `type` | string | Data type: `string`, `integer`, `boolean` |
| `operators` | array | Supported operators: `eq`, `gte`, `lte`, `in`, `like` |
| `required` | boolean | Whether the filter is mandatory |
| `example` | string | Example value |

## `pagination`

Describes how the endpoint paginates its results.

```json
{
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
      "time_window_params": {
        "start_param": null,
        "end_param": null
      }
    }
  }
}
```

### Pagination types

| `type` | Strategy | Key params |
|--------|----------|------------|
| `offset` | Offset-based | `limit_param`, `offset_param` |
| `cursor` | Cursor-based | `cursor_param`, `next_cursor_field` |
| `page` | Page number | `page_param`, `limit_param` |
| `link_header` | RFC 5988 Link header | `uses_link_header: true` |

### Pagination param fields

| Field | Description |
|-------|-------------|
| `limit_param` | Query param name for page size (e.g. `limit`, `pageSize`) |
| `offset_param` | Query param name for offset (offset pagination) |
| `max_limit` | Maximum allowed page size (null = no limit) |
| `cursor_param` | Query param name for cursor token (cursor pagination) |
| `next_cursor_field` | Response field containing the next cursor value |
| `page_param` | Query param name for page number (page pagination) |
| `uses_link_header` | Whether pagination uses HTTP Link headers |
| `time_window_params.start_param` | Query param for time window start |
| `time_window_params.end_param` | Query param for time window end |

## `replication_filter_mapping`

Maps response record fields to filter parameters for incremental replication. The pipeline runner uses this to request only records newer than the last sync.

```json
{
  "replication_filter_mapping": {
    "created": "createdDateStart"
  }
}
```

This means: "the `created` field in each response record maps to the `createdDateStart` query filter". On incremental sync, the runner passes the max `created` value from the previous run as `createdDateStart` to fetch only new records.

## Versioning

Endpoint records are versioned. Only changes to `endpoint_schema` trigger a version bump. Changes to `filters`, `pagination`, `replication_filter_mapping`, or other attributes are applied in-place (PATCH) without creating a new version.

Version detection uses a SHA256 content hash (`_content_hash`) computed over the `endpoint_schema` field. The hash is canonicalized — dict keys are sorted and lists of dicts with a `name` key (e.g. columns) are sorted by name — so reordering fields does not trigger a false version bump.

## DB Connector Endpoints

Database connector endpoints (`method: "DATABASE"`) use the same table and API but with a different `endpoint_schema` structure:

| Attribute | Type | Description |
|-----------|------|-------------|
| `endpoint` | string | Schema-qualified table path: `schema/table` (e.g. `public/wise_transfers`) |
| `method` | string | Always `"DATABASE"` |
| `endpoint_schema.columns` | array | Column definitions with `name`, `type`, `nullable`, `default`, `autoincrement`, `comment` |
| `endpoint_schema.primary_keys` | array | List of primary key column names |

No `filters`, `pagination`, or `replication_filter_mapping` — those are API-specific.

```json
{
  "endpoint": "public/wise_transfers",
  "method": "DATABASE",
  "endpoint_schema": {
    "columns": [
      { "name": "id", "type": "BIGINT", "nullable": false, "default": null, "autoincrement": false, "comment": null },
      { "name": "status", "type": "VARCHAR(50)", "nullable": true, "default": null },
      { "name": "created", "type": "TIMESTAMP", "nullable": true, "default": null },
      { "name": "source_value", "type": "NUMERIC(18, 2)", "nullable": true, "default": null },
      { "name": "_synced_at", "type": "TIMESTAMP", "nullable": true, "default": "now()" }
    ],
    "primary_keys": ["id"]
  }
}
```

## Connector Summary

After creating or updating endpoints for a connector, update the connector summary file with an **Endpoints** section. The file for each connector is stored in S3 at `s3://analitiq-platform-specs-{ENV}/connectors/{connector_id}.md`.

The section should include:

1. **Summary table** of all endpoints with columns: Endpoint, Filters, Pagination, Replication.
2. **Per-endpoint details** listing response schema fields, filter params, pagination params, and replication mapping.
3. **Explicit `${placeholder}` documentation** — list every `${placeholder}` used in endpoint paths and explain what it resolves to. Placeholders in endpoint paths (e.g. `${api_key}`, `${subdomain}`) are resolved at runtime from the connection's S3 secret or DynamoDB attributes. Each placeholder must trace to either a `form_fields` entry on the connector or a value stored in the connection secret.

Example placeholder documentation:

```
### Placeholders in endpoint paths

| Placeholder | Source | Description |
|-------------|--------|-------------|
| `${api_key}` | `form_fields` → `api_key` (type: text, stored in DynamoDB) | Yotpo App Key, used as the store ID in API paths |
```

If an endpoint path contains no placeholders, note that explicitly (e.g. "No placeholders — endpoint path is static").

## Complete API Endpoint Example (Wise Transfers)

```json
{
  "connector_id": "0b1b1d31-35ae-4047-a27f-151535fe5531",
  "endpoint_id": "5a4b9e21-441f-4bc7-9d5e-41917b4357e6",
  "endpoint": "/v1/transfers",
  "method": "GET",
  "version": 1,
  "endpoint_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Transfers List",
    "description": "Returns an array of transfer objects for a given profile",
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "id": { "type": "integer", "description": "Transfer ID" },
        "status": { "type": "string", "description": "Transfer status" },
        "created": { "type": "string", "format": "date-time", "description": "Timestamp when transfer was created" },
        "sourceCurrency": { "type": "string", "description": "Source currency code" },
        "targetCurrency": { "type": "string", "description": "Target currency code" },
        "sourceValue": { "type": "number", "description": "Amount in source currency" },
        "targetValue": { "type": "number", "description": "Amount in target currency" },
        "rate": { "type": "number", "description": "Exchange rate value" },
        "user": { "type": "integer", "description": "Your user ID" },
        "targetAccount": { "type": "integer", "description": "Recipient account ID" },
        "hasActiveIssues": { "type": "boolean", "description": "Pending issues blocking execution?" },
        "details": {
          "type": "object",
          "properties": {
            "reference": { "type": "string", "description": "Payment reference text" }
          }
        },
        "originator": {
          "nullable": true,
          "type": "object",
          "properties": {
            "name": {
              "type": "object",
              "properties": {
                "fullName": { "type": "string" },
                "givenName": { "type": "string" },
                "familyName": { "type": "string" },
                "middleNames": { "type": "array", "items": { "type": "string" } }
              }
            },
            "address": {
              "type": "object",
              "properties": {
                "city": { "type": "string" },
                "countryCode": { "type": "string" },
                "firstLine": { "type": "string" },
                "postCode": { "type": "string" }
              }
            }
          }
        }
      }
    }
  },
  "filters": {
    "createdDateStart": {
      "description": "Starting date to filter transfers, inclusive",
      "type": "string",
      "operators": ["gte"],
      "required": false,
      "example": "2018-12-15T00:00:00.000Z"
    },
    "createdDateEnd": {
      "description": "Ending date to filter transfers, inclusive",
      "type": "string",
      "operators": ["lte"],
      "required": false,
      "example": "2018-12-30T23:59:59.999Z"
    },
    "status": {
      "description": "Comma separated list of status codes",
      "type": "string",
      "operators": ["eq", "in"],
      "required": false
    },
    "sourceCurrency": {
      "description": "Source currency code",
      "type": "string",
      "operators": ["eq"],
      "required": false
    },
    "targetCurrency": {
      "description": "Target currency code",
      "type": "string",
      "operators": ["eq"],
      "required": false
    },
    "profile": {
      "description": "User profile ID (defaults to personal profile if omitted)",
      "type": "integer",
      "operators": ["eq"],
      "required": false
    },
    "limit": {
      "description": "Maximum number of records",
      "type": "integer",
      "operators": ["eq"],
      "required": false
    },
    "offset": {
      "description": "Starting record number",
      "type": "integer",
      "operators": ["eq"],
      "required": false
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
      "time_window_params": {
        "start_param": null,
        "end_param": null
      }
    }
  },
  "replication_filter_mapping": {
    "created": "createdDateStart"
  }
}
```
