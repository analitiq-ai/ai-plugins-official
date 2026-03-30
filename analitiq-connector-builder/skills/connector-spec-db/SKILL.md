---
name: connector-spec-db
disable-model-invocation: true
description: >
  Database connector specification knowledge. Contains database auth configuration,
  driver and SSH settings, and database connector examples. Load when creating or modifying
  a database connector definition (connector.json).
---

# Database Connector Specification

## Supporting Files

- [spec-form-based-db.md](spec-form-based-db.md) — database form field definitions, driver configs, SSH tunnel settings
- `examples/` — complete connector.json examples (postgresql, mysql)

## Step 1: Read the Matching Example

Read from `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-db/examples/`:

- `postgresql-connector.json` — PostgreSQL with SSH tunnel support
- `mysql-connector.json` — MySQL with SSH tunnel support

## Step 2: Read the Detailed Specification

Read `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-db/spec-form-based-db.md` for the full database connector schema including:
- Additional database attributes (`driver`, `enable_ssh`)
- Auth configuration (`auth.type: "db"`, `auth.authorize` test connection)
- Form field conventions (host, port, database, username, password)

## Step 3: Build the Connector JSON

### Quick Reference — Database Connector Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `driver` | string | yes | Database driver name (e.g. `"postgresql"`, `"mysql"`) |
| `enable_ssh` | boolean | yes | Whether SSH tunnel fields are shown in the form |
| `auth.type` | string | yes | Always `"db"` for database connectors |
| `auth.authorize` | object | no | Test connection endpoint (url, method, body) |

Database `enable_ssh` attribute would be set to 'false' by default.
