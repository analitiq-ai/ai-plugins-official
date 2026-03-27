# Connectors

A connector is a JSON object stored in the `connectors` DynamoDB table that defines a standard interface for connecting to an external system.
Each connector is stored as a separate row, keyed by `connector_id` with a `SlugIndex` GSI on `slug`.

When a user creates a connection to a system (e.g. Xero, Postgres, S3), the system saves it as a **connection** in the `connections` table.
Connections hold user-specific attributes (e.g. API key, OAuth token, host, database name).
The actual secrets (tokens, passwords, keys) are stored in S3 at `analitiq-secrets-{env}/connections/{client_id}/{connection_id}` and merged into connection objects at runtime.

## Connector Types

Connectors are split into 3 global types via `connector_type`:

| `connector_type` | Description | Examples |
|---|---|---|
| `api` | REST/HTTP APIs | Xero, Shopify, Salesforce, Google Analytics |
| `database` | SQL/NoSQL databases | PostgreSQL, MySQL, MongoDB, BigQuery, Snowflake |
| `other` | File-based and object storage | S3, SFTP, flat files (CSV, JSON) |

## Common Attributes

Every connector, regardless of type, has these root attributes:

| Attribute | Type | Required | Description                                             |
|---|---|---|---------------------------------------------------------|
| `connector_id` | string (UUID) | yes | Unique identifier (partition key)                       |
| `connector_name` | string | yes | Display name (e.g. "Xero", "PostgreSQL")                |
| `connector_type` | string | yes | One of: `api`, `database`, `other`                      |
| `slug` | string | yes | URL-safe identifier (e.g. "xero", "postgresql"). GSI key |
| `connector_group_id` | string (UUID) | yes | Groups related connectors (e.g. all Google connerctors) |
| `form_fields` | array | yes | Defines what the user sees when creating a connection   |
| `auth` | object | yes | Authentication configuration (structure varies by type) |
| `connector_descr` | string | no | Human-readable description of the connector             |

### `form_fields`

Controls the connection creation UI. Each entry is an object:

| Field | Description |
|---|---|
| `name` | Field identifier, used as the key when storing the value |
| `label` | Human-readable label shown in the UI |
| `type` | `text` (plain input, stored in DynamoDB), `password` (masked, stored in S3), `oauth2` (triggers OAuth redirect), `select` (dropdown) |
| `required` | Whether the field must be filled |
| `secret` | Field is a secret (like password or token) |
| `disabled` | User is not allowed to edit the field |
| `hidden` | The user does not see the field |
| `default` | Default text or value |

## Type-Specific Structure

### `api` Connectors

API connectors define HTTP-based integrations with external services.
See [spec-auth-flows.md](spec-auth-flows.md) for the full API connector schema, auth flows, headers, placeholders, and examples.

Additional root attributes for API connectors:

| Attribute | Type | Description |
|---|---|---|
| `client_required` | boolean | Whether the API requires a registered app/client on the target platform |
| `base_url` | string | Base URL for API data requests (supports `${placeholder}`) |
| `headers` | object | Headers sent with every API data request |
| `timeout` | integer | Request timeout in seconds |
| `rate_limit` | object | Rate limiting parameters (`max_requests`, `time_window_seconds`) |
| `post_auth_steps` | array | Steps taken after authentication (optional) |

`auth.type` values for API connectors: `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`.

### `database` and `other` Connectors

Database connectors define connections to SQL and NoSQL databases. Other connectors cover file-based and object storage systems (S3, SFTP, flat files). Both use a form-based flow.
See [spec-form-based.md](spec-form-based.md) for schemas and examples.

## Connectors vs Connections

| | Connector | Connection |
|---|---|---|
| **Table** | `connectors` | `connections` |
| **Scope** | Global (one per system) | Per-client (one per user setup) |
| **Contains** | Schema, auth type, form fields, defaults | User-specific values, references connector |
| **Secrets** | Connector-level S3 secret at `api/{connector_id}` (e.g. OAuth client_id/secret) | Connection-level S3 secret at `connections/{client_id}/{connection_id}` |

At runtime, the system merges connector defaults with connection-specific values, resolving all `${placeholder}` tokens from S3 secrets.

## Platform Secrets and the `_public` Allowlist

Each connector can have a platform-level S3 secret stored at `api/{connector_id}`. This secret contains shared credentials (e.g. `client_id`, `client_secret`) used across all connections for that connector.

### Structure

```json
{
  "client_id": "abc123",
  "client_secret": "supersecret",
  "_public": ["client_id"]
}
```

| Key | Description |
|---|---|
| `_public` | Array of key names that are safe to expose to the frontend. Only these keys are used when resolving `${placeholder}` tokens in the `GET /connectors/{id}` response. |

### Resolution Rules

| Consumer | Secret keys used | Purpose |
|---|---|---|
| `GET /connectors/{id}` | Only `_public` keys | Resolve placeholders in connector metadata returned to frontend (e.g. `${client_id}` in `auth.authorize_url`) |
| `connection-options` Lambda | All keys (merged with connection secrets) | Resolve placeholders in `post_auth_steps` API calls |
| `oauth2-callback` Lambda | All keys | Token exchange with provider |
| `oauth2-token-refresh` Lambda | All keys | Token refresh with provider |
| Pipeline runner (Batch) | All keys (merged with connection secrets) | Resolve placeholders in runtime API headers/URLs |

### Two-Tier Secret Merge

Server-side consumers that make API calls on behalf of a connection merge both secret sources before resolving placeholders:

```python
platform_secrets = k2m_aws.get_aws_service_secret(connector_id)      # api/{connector_id}
connection_secrets = k2m_aws.get_connection_secret(...)    # connections/{client_id}/{connection_id}
context = {**platform_secrets, **connection_secrets}                   # connection wins on conflict
```

This enables connectors like Twitch (`Client-Id: ${client_id}`) and Amazon Advertising (`Amazon-Advertising-API-ClientId: ${client_id}`) where platform credentials are required in every API request alongside user-specific tokens.

### Adding a New Platform Secret

1. Upload the secret to S3: `s3://analitiq-secrets-{env}/api/{connector_id}`
2. Include a `_public` array listing keys safe for frontend exposure
3. Keys **not** in `_public` are only available to server-side Lambdas and the pipeline runner

## Connector Summary

Each connector has a summary file stored in S3 at `s3://analitiq-platform-specs-{ENV}/connectors/{connector_id}.md`.

When creating or editing a connector summary, document **every `${placeholder}`** used anywhere in the connector — in `base_url`, `headers`, `auth` operations (`authorize.url`, `token_exchange.url`/`headers`/`body`, `refresh.url`/`headers`/`body`), `post_auth_steps`, and endpoint paths. For each placeholder, specify:

| Column | Description |
|--------|-------------|
| Placeholder | The `${name}` token exactly as it appears |
| Location | Where it is used (e.g. `headers.Authorization`, `base_url`, `auth.token_exchange.body`, endpoint path) |
| Source | Where the value comes from: `form_fields` entry (with type: text/password/oauth2), OAuth token response field, `post_auth_steps` result, connector S3 secret (`api/{connector_id}`), or derived value (e.g. `basic_auth`) |
| Storage | Where the resolved value is stored: DynamoDB (text fields), S3 connection secret (password fields, OAuth tokens), or S3 connector secret (platform credentials) |

Example:

```
### Placeholders

| Placeholder | Location | Source | Storage |
|-------------|----------|--------|---------|
| `${client_id}` | `auth.authorize.url`, `auth.token_exchange.body` | connector S3 secret | S3 `api/{connector_id}` |
| `${client_secret}` | `auth.token_exchange.body` | connector S3 secret | S3 `api/{connector_id}` |
| `${access_token}` | `headers.Authorization` | OAuth token response | S3 `connections/{client_id}/{connection_id}` |
| `${tenant_id}` | `headers.xero-tenant-id` | `post_auth_steps` result | S3 `connections/{client_id}/{connection_id}` |
| `${site}` | `base_url` | `form_fields` → `site` (type: text) | DynamoDB connection record |
```