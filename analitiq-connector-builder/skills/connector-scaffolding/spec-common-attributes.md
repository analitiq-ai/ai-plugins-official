# Connectors

A connector is a JSON definition that describes how to connect to an external system — auth type, required credentials, base URL, headers, and rate limits. Users later create connections from this template by filling in their own credentials.

## Connector Types

Connectors are split into 3 global types via `connector_type`:

| `connector_type` | Description | Examples |
|---|---|---|
| `api` | REST/HTTP APIs | Xero, Shopify, Salesforce, Google Analytics |
| `database` | SQL/NoSQL databases | PostgreSQL, MySQL, MongoDB, BigQuery, Snowflake |
| `other` | File-based and object storage | S3, SFTP, flat files (CSV, JSON) |

## Common Attributes

Every connector, regardless of type, has these root attributes:

| Attribute | Type | Required | Description                                                      |
|---|---|---|------------------------------------------------------------------|
| `connector_name` | string | yes | Display name (e.g. "Xero", "PostgreSQL")                         |
| `connector_type` | string | yes | One of: `api`, `database`, `other`                               |
| `slug` | string | yes | URL-safe identifier (e.g. "xero", "postgresql"). GSI key         |
| `category_id` | string | yes | UUID of the connector category (`connector_group_id` from the public [categories.json](https://raw.githubusercontent.com/analitiq-dip-registry/.github/main/categories.json)). Chosen in Phase 1.6 of `connector-wizard`. |
| `form_fields` | array | no | Defines the credential or parameter fields the user must fill in |
| `auth` | object | no | Authentication configuration (structure varies by type)          |
| `connector_descr` | string | no | Human-readable description of the connector                      |
| `connector_image` | string | no | Logo/image URL                                                   |
| `api_doc_url` | string | no | Link to API documentation for reference by AI agents             |

### `form_fields`

Controls the credential/parameter form shown to the user. Each entry is an object:

| Field | Description |
|---|---|
| `name` | Field identifier, used as the key when storing the value |
| `label` | Human-readable label shown in the UI |
| `type` | `text` (plain input), `password` (masked input), `oauth2` (triggers OAuth redirect), `select` (dropdown) |
| `required` | Whether the field must be filled |
| `secret` | Field is a secret (like password or token) |
| `disabled` | User is not allowed to edit the field |
| `hidden` | The user does not see the field |
| `default` | Default text or value |

## Type-Specific Structure

### `api` Connectors

API connectors define HTTP-based integrations with external services.
See [spec-auth-flows.md](../connector-spec-api/spec-auth-flows.md) for the full API connector schema, auth flows, headers, placeholders, and examples.

Additional root attributes for API connectors:

| Attribute | Type | Description |
|---|---|---|
| `client_required` | boolean | Whether the API requires a registered app/client on the target platform (default: false) |
| `base_url` | string | Base URL for API data requests (supports `${placeholder}`). Nullable for dynamic URL connectors |
| `headers` | object | Headers sent with every API data request (default: `{}`) |
| `timeout` | integer | Request timeout in seconds (min: 1) |
| `requests_per_second` | object | Rate limiting parameters (`max_requests`, `time_window_seconds`) |
| `post_auth_steps` | array | Steps taken after authentication (optional) |
| `host` | string | Override host URL (optional) |
| `max_connections` | integer | Max concurrent connections (min: 1, optional) |

`auth.type` values for API connectors: `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`.

### `database` and `other` Connectors

Database connectors cover SQL and NoSQL databases. Other connectors cover file-based and object storage systems (S3, SFTP, flat files). Both use a form-based auth flow.
See [spec-form-based-db.md](../connector-spec-db/spec-form-based-db.md) and [spec-form-based-storage.md](../connector-spec-storage/spec-form-based-storage.md) for schemas and examples.

At runtime, the platform resolves all `${placeholder}` tokens from stored parameters and credentials before making requests.

