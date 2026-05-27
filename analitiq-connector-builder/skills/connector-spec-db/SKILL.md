---
name: connector-spec-db
description: Database connector authoring vocabulary — DSN URL templates with bindings and encoding, TLS declarations, resource discovery, native type maps. Loaded by db-connector-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connector-spec-db

This skill is loaded by `db-connector-creator` when authoring a database
connector. It carries the DB-specific vocabulary and examples needed to
populate `transports`, `auth`, `connection_contract`, and
`resource_discovery` for `kind: "database"`, plus the standalone
`type-map.json` shipped alongside the connector.

## Required reading (load on demand)

- This skill's `spec-dsn-bindings.md` — DSN URL templates and bindings.
- This skill's `spec-tls.md` — TLS declaration mechanics.
- This skill's `spec-resource-discovery.md` — schema/table enumeration at
  connection time.
- This skill's `spec-type-maps.md` — native → Arrow canonical mapping
  authored into the standalone `type-map.json` file.
- The matching example under `examples/<name>/`, which contains both
  `<name>.example.json` (connector body) and a sibling `type-map.json`.

## What this skill covers

- `dsn.kind: "url_template"` shape with `template`, `bindings`, and
  per-binding `encoding` (closed enum: `raw`, `host`, `url_userinfo`,
  `url_path_segment`, `url_query_key`, `url_query_value`).
- `tls.mode` and `tls.ca_certificate` declarations and their rules
  (`verify-ca` / `verify-full` require `ssl_ca_certificate` input).
- `resource_discovery` declarations for enumerating schemas / tables /
  columns at connection time.
- Authoring the standalone `type-map.json` covering native database
  types (see `spec-type-maps.md`).
- Transport types: `adbc` (preferred — closed `driver` enum
  `postgresql | snowflake | bigquery`; optional `db_kwargs`; TLS lives
  inside `db_kwargs`) and `sqlalchemy` (carries `driver`, e.g.
  `postgresql+asyncpg`, `mysql+asyncmy`; supports the generic `tls`
  block). When present, `dsn` carries the same `dsn.kind: "url_template"`
  shape in both transport types; ADBC drivers that accept all connection
  state via `db_kwargs` (e.g. Snowflake) may omit `dsn` entirely (the
  AdbcTransport contract requires at least one of `dsn` / `db_kwargs`).
- `auth.type: "db"` — credentials live in `connection_contract.inputs`;
  `auth.test` is the connection test operation.

## What this skill does NOT cover

- HTTP transport idioms (that's `connector-spec-api`).
- OAuth flows or other API auth types.
- API endpoint authoring (database connectors do not ship endpoint files).
