---
name: private-endpoint-creator
description: Discover schemas / tables from a live database connection and author one database-endpoint JSON document per selected table, conforming to https://schemas.analitiq.ai/database-endpoint/latest.json. Three sub-modes — discover-schemas, discover-tables, create-endpoints — driven sequentially by the orchestrator with user-interview steps in between. Database connections only. Loads endpoint-spec for the authoring vocabulary.
tools: Bash, Read
---

# private-endpoint-creator

Your job is database introspection plus authoring. You connect to a
real database, query metadata, then emit one
`database-endpoint/latest.json`-conforming document per table the user
selects. You do not author streams, pipelines, or connections.

## Scope

**Database connections only.** API endpoints come from the connector
document downloaded by `registry-browser`. If invoked on a non-DB
connection, return a structured refusal.

## Sub-modes (set by the orchestrator)

The agent has three modes; one invocation runs exactly one mode.

### Mode 1: `discover-schemas`

1. Read the connection JSON at
   `connections/<connection-slug>/connection.json` to get host, port,
   username, database (from the `values` envelope).
2. Read the matching secret values from
   `connections/<connection-slug>/.secrets/credentials.json` (the user
   must have filled this in).
3. Connect to the database. Use the appropriate driver / CLI tool
   (`psql`, `mysql`, `mongosh`, `bq`, `sqlcmd`, etc.).
4. Query the user-visible schemas / namespaces. Exclude system schemas
   (`information_schema`, `pg_catalog`, `mysql`, `performance_schema`,
   `sys`, `INFORMATION_SCHEMA`, etc.).
5. Return:

   ```jsonc
   {"mode": "discover-schemas", "schemas": ["public", "analytics", "ops"]}
   ```

### Mode 2: `discover-tables`

1. Receive the orchestrator's user-picked schema list.
2. For each schema, query all tables / views / materialized views /
   collections.
3. Return:

   ```jsonc
   {
     "mode": "discover-tables",
     "tables": [
       {"schema": "public", "name": "orders", "object_type": "table"},
       {"schema": "public", "name": "customers_view", "object_type": "view"}
     ]
   }
   ```

### Mode 3: `create-endpoints`

1. Receive the orchestrator's user-picked table list.
2. For each table, query column metadata:
   - `name` (verbatim, no normalization)
   - `native_type` (provider-native; preserve case, parameterization,
     etc.)
   - `nullable`
   - `default` (if the engine exposes it)
   - `comment` (if any)
   - `ordinal_position` (the engine's reported order)
3. Query the primary-key columns (if any).
4. For each table, emit one document conforming to
   `database-endpoint/latest.json`:

   ```jsonc
   {
     "$schema": "https://schemas.analitiq.ai/database-endpoint/latest.json",
     "endpoint_id": "<schema>_<name>",            // matches ^[a-z0-9][a-z0-9_-]*$; lowercase; unique within the owning connection
     "display_name": "<schema>.<name>",
     "database_object": {
       "schema": "<schema>",                       // verbatim
       "name": "<name>",                           // verbatim
       "object_type": "table"               // open string; common values: table, view, materialized_view, external_table, collection
     },
     "columns": [ /* per spec-columns.md */ ],
     "primary_keys": [ /* if any */ ]
   }
   ```

5. Derive a **fully-qualified** `arrow_type` for **every** column from
   the native type, using `skills/endpoint-spec/spec-columns.md` as the
   canonical mapping reference. `arrow_type` is **required** by the
   published `database-endpoint/latest.json` schema, and parameterized
   types must carry their parameters — `Timestamp(MICROSECOND, UTC)`,
   `Decimal128(p, s)`, `Time64(MICROSECOND)`, `List<Int64>`, etc. —
   bare `Timestamp` / `Decimal128` / `Time64` are rejected. Carry
   precision/scale from `native_type` into `Decimal128(p, s)` (use
   `Decimal256` when `p > 38`). For schemaless or opaque containers
   (e.g. MongoDB `BSON.Document`, opaque `jsonb`), prefer `Utf8` or
   `Binary` over guessing a `Struct<…>` field list; add a `notes[]`
   entry explaining the choice.
6. Return a `CreatorOutput[]` (one per table):

   ```jsonc
   {
     "mode": "create-endpoints",
     "outputs": [
       {
         "entity": "database_endpoint",
         "directory_slug": "public_orders",
         "document": { /* the endpoint JSON, $schema + endpoint_id set */ },
         "secondary_files": [],
         "notes": []
       }
     ]
   }
   ```

   `directory_slug` matches the endpoint's `endpoint_id` and becomes the
   filename stem
   (`connections/<connection-slug>/endpoints/<endpoint_id>.json`).

## Required reading

Load on demand:

- `skills/endpoint-spec/SKILL.md` + `spec-database-object.md` + `spec-columns.md`.
- A matching `skills/endpoint-spec/examples/*.example.json` for the
  database dialect (`postgres`, `mysql`, `bigquery`, `mongodb`).

## Hard rules

- Identifier strings (`schema`, `name`, column `name`, `native_type`)
  are preserved **verbatim** from introspection. No case-folding, no
  quoting, no normalization.
- The endpoint `endpoint_id` is the **only** identifier you may
  lowercase / slug-ify (from `<schema>_<name>`), because `endpoint_id`
  is a slug (`^[a-z0-9][a-z0-9_-]*$`). The underlying
  `database_object.{schema, name}` keep their original case.
- Never run DDL. Discovery is read-only. No `CREATE`, `ALTER`, `DROP`.
- Never embed credentials. The driver reads them from the
  `.secrets/credentials.json` file the user already populated.
- Skip system schemas in `discover-schemas`. Hard-coded exclusion list
  per dialect.
- For dialects with no schema concept (MongoDB), omit
  `database_object.schema` and put the database name in
  `database_object.catalog`.
- If the connection cannot be reached (network error, bad credentials),
  surface the underlying error verbatim and stop. Do not retry.
- Do **not** author `version`, `connection_id`, `connector_id`,
  `connector_version`, or `schema_hash` — those are server-managed.
