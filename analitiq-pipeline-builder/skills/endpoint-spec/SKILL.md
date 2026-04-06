---
name: endpoint-spec
disable-model-invocation: true
description: >
  Private endpoint specification for database connections. Contains the DB endpoint schema
  format including column definitions and primary keys. Used by the private-endpoint-creator
  agent to create endpoint files after discovering schemas and tables from a live database
  connection. Not applicable to API connectors (their endpoints are public and pre-defined
  in the connector repo).
---

# Private Endpoint Specification

Private endpoints are database schemas/tables discovered from a live connection. Unlike API
endpoints (which are pre-defined in connector repos), private endpoints are specific to each
user's database and are created inside the connection directory after the connection is set up.

## DB Endpoint JSON Structure

```json
{
  "endpoint": "public/users",
  "method": "DATABASE",
  "version": 1,
  "endpoint_schema": {
    "columns": [
      {
        "name": "id",
        "type": "integer",
        "nullable": false,
        "autoincrement": true
      },
      {
        "name": "email",
        "type": "character varying",
        "nullable": false
      },
      {
        "name": "created_at",
        "type": "timestamp with time zone",
        "nullable": true
      }
    ],
    "primary_keys": ["id"]
  }
}
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint` | string | yes | Logical endpoint name: `{schema}/{table}` (e.g., `public/users`) |
| `method` | string | yes | Always `"DATABASE"` for DB endpoints |
| `version` | integer | yes | Schema version, starts at `1` |
| `endpoint_schema` | object | yes | Schema metadata (columns + primary keys) |

### endpoint_schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `columns` | array | yes | Column definitions for the table/view |
| `primary_keys` | array of strings | no | Column names forming the primary key |

### Column Definition

Each column in the `columns` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Column name |
| `type` | string | yes | Native database type (e.g., `integer`, `character varying`, `timestamp with time zone`) |
| `nullable` | boolean | no | Whether the column allows NULL values |
| `default` | any | no | Default value if defined |
| `autoincrement` | boolean | no | Whether the column auto-increments |
| `comment` | string | no | Column comment from the database |

## Endpoint Naming

The `endpoint` field uses the format `{schema}/{table}`:
- PostgreSQL: `public/users`, `analytics/events`
- MySQL: `mydb/orders` (MySQL uses database name as schema)

## API Endpoint Filters with Placeholders

API endpoints (pre-defined in connector repos) may include a `filters` object. Filters can
reference connection parameters using `${param_name}` syntax in their `default` field. At
runtime, the engine resolves these from `connection.parameters`.

```json
{
  "filters": {
    "profile": {
      "type": "integer",
      "required": true,
      "default": "${profile_id}"
    }
  }
}
```

The filter key (`profile`) becomes the query parameter name. The `${profile_id}` references
the connection parameter name. These are often different — the filter key is the API query
parameter name, while the placeholder references the `field_name` from `post_auth_steps`
stored in `connection.parameters`.

The engine resolves these placeholders automatically at runtime: it reads the source
connection's `parameters` dict, stringifies all non-dict values into a flat lookup, and
runs placeholder expansion on the endpoint's filters and fields. No stream-side
`source.parameters` config is needed for this — unresolved placeholders are left as-is.

## Discovery Process

1. Connect to the database using connection parameters + credentials from `.secrets/`
2. Query `information_schema.tables` (or equivalent) to list schemas and tables
3. For each selected table, query `information_schema.columns` for column metadata
4. Query primary key constraints
5. Create one endpoint JSON file per table

## Output

Save each endpoint in the connection's `endpoints/` directory:
```
connections/{connection-name}/endpoints/{schema}-{table}.json
```

Use the schema-table combination as the filename with a hyphen separator:
- `public/users` → `public-users.json`
- `analytics/events` → `analytics-events.json`
