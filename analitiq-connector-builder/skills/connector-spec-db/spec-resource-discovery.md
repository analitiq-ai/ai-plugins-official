# Resource discovery (databases)

How database connectors declare the discovery strategy that the runtime
uses to enumerate schemas, tables, and columns.

## Shape

```json
{
  "resource_discovery": {
    "strategy": "information_schema",
    "transport_ref": "database",
    "implementation": { "type": "builtin" },
    "options": {
      "exclude_schemas": ["information_schema", "pg_catalog"]
    },
    "produces": ["connection.endpoints", "connection.type_map"],
    "triggers": {
      "list_resources": "on_activation",
      "describe_resource": "on_resource_selected"
    }
  }
}
```

## Required fields

- `strategy` — registered strategy ID. Common values:
  - `information_schema` for ANSI-SQL databases that expose
    `information_schema`.
  - `snowflake_account_usage` for Snowflake.
  - Provider-specific IDs as appropriate. The strategy must already be
    registered with the engine, or a `connector_plugin` implementation
    must be declared.

## Optional fields

- `transport_ref` — which transport to use for discovery. Defaults to
  `default_transport`.
- `implementation` — `{ "type": "builtin" }` for engine-shipped
  strategies (the common case), or
  `{ "type": "connector_plugin", "entrypoint": "module.path:ClassName" }`
  to ship strategy code with the connector package.
- `options` — strategy-specific declarative options (e.g.
  `exclude_schemas`).
- `produces` — array of `connection.endpoints` and/or
  `connection.type_map`. Most database connectors produce both.
- `triggers` — when discovery actions run:
  - `list_resources`: `on_activation` | `on_connection_selected` | `on_resource_selected` | `on_demand` | `scheduled`.
  - `describe_resource`: same enum.

## Rules

- The discovery transport may be the same as the data transport, or a
  separate discovery-only transport with restricted credentials.
- Discovery output is connection-scoped, not connector-scoped.
- Connector-level `type_maps` provide the seed mapping for native types
  encountered during discovery; connection-level type maps may extend or
  override per-connection where needed (e.g. PostGIS `GEOMETRY` only on
  some PostgreSQL connections).

## Common pitfalls

- Don't try to ship database endpoints directly from the connector. They
  are produced from discovery output at runtime.
- Don't embed credentials in `options`. Auth runs separately.
- Don't author a custom strategy in `implementation` unless one of the
  builtin IDs doesn't fit. Most connectors should use builtin
  strategies.
