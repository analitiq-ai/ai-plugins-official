---
name: connector-spec-db
description: Database connector authoring vocabulary — driver selection, DSN URL templates with bindings and encoding, TLS declarations, resource discovery, read/write type maps, and the Python package files. Loaded by db-connector-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connector-spec-db

This skill is loaded by `db-connector-creator` when authoring a database
connector. It carries the DB-specific vocabulary and examples needed to
populate `transports`, `auth`, `connection_contract`, and
`resource_discovery` for `kind: "database"`, plus the standalone
`type-map-read.json` / `type-map-write.json` shipped alongside the
connector and the package files (`connector.py`, `__init__.py`,
`requirements.txt`, `pyproject.toml`) that make the connector an
installable Python package.

## Required reading (load on demand)

- This skill's `spec-driver-selection.md` — the transport/driver
  decision order (ADBC → Flight SQL → native bulk path → batched
  INSERT) and the async-driver constraint.
- This skill's `spec-dsn-bindings.md` — DSN URL templates and bindings.
- This skill's `spec-tls.md` — TLS declaration mechanics.
- This skill's `spec-resource-discovery.md` — schema/table enumeration at
  connection time.
- This skill's `spec-type-maps.md` — the read map (native → Arrow,
  `type-map-read.json`) and the write map (Arrow → native DDL,
  `type-map-write.json`), incl. the uppercase-pattern rule and the
  direction inversion.
- This skill's `spec-connector-package.md` — package layout,
  `pyproject.toml` + entry points, dialect hooks, CDK import rules.
- The matching example under `examples/<name>/`, which contains
  `<name>.example.json` (connector body) plus sibling
  `type-map-read.json` and `type-map-write.json`.

## What this skill covers

- `dsn.kind: "url_template"` shape with `template`, `bindings`, and
  per-binding `encoding` (closed enum: `raw`, `host`, `url_userinfo`,
  `url_path_segment`, `url_query_key`, `url_query_value`).
- `tls.mode` and `tls.ca_certificate` declarations and their rules
  (`verify-ca` / `verify-full` require `ssl_ca_certificate` input).
  **SQLAlchemy-only**: ADBC transports express TLS via `db_kwargs`
  entries (e.g. `adbc.postgresql.sslmode`) — they have no `tls` block.
- `resource_discovery` declarations for enumerating schemas / tables /
  columns at connection time.
- Authoring the standalone `type-map-read.json` (native → Arrow) and
  `type-map-write.json` (Arrow → native DDL render rules; full
  canonical-vocabulary coverage) — see `spec-type-maps.md`.
- The connector package files and dialect hooks — see
  `spec-connector-package.md`.
- Transport types, chosen per the `spec-driver-selection.md` decision
  order: `adbc` (closed `driver` enum
  `postgresql | snowflake | bigquery`; carries `dsn` and/or `db_kwargs`
  — **the AdbcTransport contract requires at least one of the two**;
  TLS lives inside `db_kwargs`) and `sqlalchemy` (carries an **async**
  `driver`, e.g. `postgresql+asyncpg`, `mysql+aiomysql`; supports the
  generic `tls` block). When present, `dsn` carries the same
  `dsn.kind: "url_template"` shape in both transport types; ADBC
  drivers that accept all connection state via `db_kwargs` (e.g.
  Snowflake) may omit `dsn` entirely.
- `auth.type: "db"` — credentials live in `connection_contract.inputs`;
  `auth.test` is the connection test operation.

## What this skill does NOT cover

- HTTP transport idioms (that's `connector-spec-api`).
- OAuth flows or other API auth types.
- API endpoint authoring (database connectors do not ship endpoint files).
