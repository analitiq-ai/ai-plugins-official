# Connector package files

A database connector is an installable Python package. The engine image
ships NO database drivers; each connector brings its own. The engine
resolves a connector in two steps: `kind` selects the generic fallback
class, `connector_id` selects the connector package's own class via
Python entry points.

API connectors carry **only** the definition (`connector.json`,
`type-map-read.json`, `endpoints/`) — no package files, no write map.

## Required layout

The connector root IS the Python package:

```
{connector_id}/
  definition/
    connector.json                   # declares connector_id; async/ADBC drivers only
    type-map-read.json               # native → Arrow; regex patterns UPPERCASE
    type-map-write.json              # Arrow → native; REQUIRED for kind: database
  __init__.py                        # re-exports the connector class
  connector.py                       # {Name}Dialect(SqlDialect) + {Name}Connector(GenericSQLConnector)
  requirements.txt                   # THIS connector's driver(s) only
  pyproject.toml                     # analitiq-connector-{connector_id}; see below
```

`connector_id` in `connector.json` must equal the repo/directory name —
it is the entry-point name the engine resolves.

## `pyproject.toml`

- `name = "analitiq-connector-{connector_id}"`.
- `dynamic = ["dependencies"]` +
  `[tool.setuptools.dynamic] dependencies = { file = ["requirements.txt"] }`
  — `requirements.txt` is the single source of truth for the driver.
- Package mapping (the repo root is the package):
  `packages = ["analitiq_connector_{connector_id}"]`,
  `package-dir = { "analitiq_connector_{connector_id}" = "." }`.
- Entry points — name = `connector_id`, **both roles** (read and write
  are both first-class; never ship a one-directional connector):

  ```toml
  [project.entry-points."analitiq.source_connectors"]
  {connector_id} = "analitiq_connector_{connector_id}.connector:{Name}Connector"

  [project.entry-points."analitiq.destination_connectors"]
  {connector_id} = "analitiq_connector_{connector_id}.connector:{Name}Connector"
  ```

- The CDK is provided by the engine environment — never list it as a
  dependency.

Template (postgres reference):

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "analitiq-connector-{connector_id}"
version = "0.1.0"
description = "Analitiq connector for {DisplayName}: dialect, driver, definition."
requires-python = ">=3.11"
dynamic = ["dependencies"]

[tool.setuptools.dynamic]
dependencies = { file = ["requirements.txt"] }

[tool.setuptools]
packages = ["analitiq_connector_{connector_id}"]
package-dir = { "analitiq_connector_{connector_id}" = "." }

[project.entry-points."analitiq.source_connectors"]
{connector_id} = "analitiq_connector_{connector_id}.connector:{Name}Connector"

[project.entry-points."analitiq.destination_connectors"]
{connector_id} = "analitiq_connector_{connector_id}.connector:{Name}Connector"
```

## `requirements.txt`

THIS connector's driver(s) only — the async DBAPI for SQLAlchemy
transports and/or the `adbc-driver-{driver}` wheel (+
`adbc-driver-manager`) for ADBC transports. See
`spec-driver-selection.md` for choosing. Comment non-obvious pins (e.g.
`pymysql<1.2`).

## `connector.py`

One dialect class plus one connector class:

```python
from cdk.sql.dialects import SqlDialect
from cdk.transport_factory import ca_ssl_context
from cdk.sql.generic import GenericSQLConnector


class {Name}Dialect(SqlDialect):
    name = "{dialect_name}"
    system_schemas = (...)           # catalog schemas to exclude from discovery
    ...


class {Name}Connector(GenericSQLConnector):
    dialect_class = {Name}Dialect
```

### Import rules

A connector depends only on the CDK: `cdk.sql.dialects.SqlDialect`,
`cdk.sql.generic.GenericSQLConnector`,
`cdk.transport_factory.ca_ssl_context`, `cdk.type_map` — plus the
connector's own driver and SQLAlchemy dialect helpers (e.g.
`sqlalchemy.dialects.postgresql.insert`). It never imports another
connector and never imports an engine/runtime. MariaDB ships its own
copy of the mysql-shaped dialect rather than importing the mysql
connector.

### Dialect hooks

The dialect must implement every hook its transports require — missing
hooks fail loudly with `UnsupportedDialectOperationError`:

| Transport feature | Required hook(s) |
|---|---|
| SQLAlchemy + TLS | `build_tls_connect_arg(mode, ca_pem)` — interprets the connector's declared `ssl_mode` vocabulary into the driver's connect argument (mode string, `False`, or an `SSLContext` built via `ca_ssl_context`). |
| SQLAlchemy upsert | `build_sqlalchemy_upsert(table, records, conflict_keys)` + `supports_upsert_sqlalchemy = True` (e.g. postgres `ON CONFLICT DO UPDATE`, mysql `ON DUPLICATE KEY UPDATE`). |
| ADBC upsert | `adbc_stage_table_sql(stage_qualified, target_qualified)` + `supports_upsert_adbc = True` (e.g. `CREATE TABLE … (LIKE … INCLUDING DEFAULTS)`, `CREATE TABLE … LIKE …`). |
| Discovery | `schemas_query()` and the `system_schemas` exclusion list. |
| Pre-DDL | `sqlalchemy_pre_ddl(schema_name)` when schemas must exist before `create_all` (postgres `CREATE SCHEMA IF NOT EXISTS`). |

### Structural overrides — only where the portable form is invalid

- `batch_commits_key_type(type_mapper)` — where the write map's `Utf8`
  cannot be a primary key (MySQL/MariaDB: bounded `VARCHAR(255)`; TEXT
  cannot be a MySQL primary key).
- `current_timestamp_default()` — where the DEFAULT expression must
  carry precision (MySQL/MariaDB: `CURRENT_TIMESTAMP(6)`; the bare form
  is error 1067 against a `DATETIME(6)` column).

### Type vocabulary is declarative-only

The write direction lives in `type-map-write.json` and nowhere else:
every transport (SQLAlchemy DDL, ADBC DDL, control-plane create_table)
renders column types through `dialect.render_column_type`, whose
default is the write map. A dialect overrides it ONLY for logic rules
cannot express (BigQuery's NUMERIC/BIGNUMERIC precision-range
arithmetic) — and even then delegates everything else back to the map.
**Connectors must NOT ship Python type-rendering tables.**

### Thick-path overrides

When the system needs behavior the generic base cannot express,
override just the quirky method (the thin → thick gradient). Example:
BigQuery's connector class overrides `_record_batch_commit_via_adbc`
(MERGE + rowcount collision detection, because BigQuery primary keys
are NOT ENFORCED). Systems on decision-order step 3 implement their
native bulk-load path here against the raw cursor.

## `__init__.py`

```python
"""analitiq-connector-{connector_id}: {DisplayName} connector package for Analitiq."""

from .connector import {Name}Connector, {Name}Dialect

__all__ = ["{Name}Connector", "{Name}Dialect"]
```

## Enforcement

The plugin's schema validator checks JSON documents only. Package files
are enforced by registry CI: `pip wheel --no-deps .` must build, and
the wheel must contain `analitiq_connector_{id}/connector.py` plus the
two entry points.
