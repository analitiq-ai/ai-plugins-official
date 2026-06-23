# Enum mappers

Closed-enum decision rules used by the orchestrator to classify provider
facts into schema-bound enum values. If no enum value fits, fail closed
and ask the user.

## KindMapper

| Input fact | Output `kind` |
|---|---|
| Provider is a SaaS / REST API | `api` |
| Provider is a SQL or document database | `database` |
| Provider is local file storage | `file` (storage stub only) |
| Provider is S3 / object storage | `s3` (storage stub only) |
| Provider is stdout / debug sink | `stdout` (storage stub only) |

For storage kinds the orchestrator dispatches to the stub agent which
declines until engine support lands.

## AuthTypeMapper

| Input fact (provider auth model) | Output `auth.type` |
|---|---|
| Static API key in header | `api_key` |
| HTTP basic auth (username + password) | `basic_auth` |
| OAuth2 with redirect / browser consent | `oauth2_authorization_code` |
| OAuth2 with no redirect (machine-to-machine) | `oauth2_client_credentials` |
| JWT signed locally with provider-issued key | `jwt` |
| Database username + password (and optional TLS) | `db` |
| AWS IAM, role, profile, or credential chain | `aws_iam` |
| Multi-field credential bundle that doesn't fit above | `credentials` |
| No authentication required | `none` |

## TransportTypeMapper

| Input fact | Output `transport_type` |
|---|---|
| Provider is a REST API | `http` |
| Provider is a database (decision order below) | `adbc` or `sqlalchemy` |
| Provider is local file storage | `file` |
| Provider is S3 / object storage | `s3` |
| Provider is stdout sink | `stdout` |

For databases, apply the driver-selection decision order — in this
order, stopping at the first match (full guide:
`connector-spec-db/spec-driver-selection.md`):

1. **A first-class ADBC driver exists** (the schema's
   `AdbcTransport.driver` enum is the sole validator — currently
   `postgresql`, `snowflake`, `bigquery`) → `adbc`. The driver hands
   Arrow buffers to the system's native bulk protocol; no row-by-row
   path. Redshift is libpq-compatible and takes `adbc` with driver
   `postgresql`.
2. **The server exposes an Arrow Flight SQL endpoint** → `adbc` via the
   generic Flight SQL driver. `flightsql` is **not yet in the
   `AdbcTransport.driver` enum** (`postgresql`, `snowflake`, `bigquery`),
   so this tier is currently unreachable — selecting it requires adding
   the enum value first (a schema-contract change; see
   `spec-driver-selection.md`). Ordinary MySQL/Postgres deployments do
   not expose Flight SQL.
3. **Neither, but the system has a native bulk-load protocol** →
   `sqlalchemy` (async DBAPI) for connect/DDL, with the bulk write
   implemented in the connector's own class against the raw cursor
   (the thick path).
4. **None of the above** → `sqlalchemy` (async DBAPI) with batched
   INSERT. This is the fallback, not the default — pick it last.

Never select the JDBC bridge (`adbc-driver-jdbc`): it provides the ADBC
API surface over row-by-row JDBC binding — the interface without the
performance. SQLAlchemy transports require an **async** DBAPI
(`postgresql+asyncpg`, `mysql+aiomysql`, `mariadb+aiomysql`); sync
drivers fail at connect.

## Failing closed

If the input doesn't fit any enum value:

1. Stop. Do not invent a value.
2. Surface the ambiguity to the user with the offending fact.
3. Wait for either a clarifying answer or instruction to abort.
