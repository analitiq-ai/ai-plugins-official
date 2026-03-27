---
name: connector-spec
description: >
  Connector specification knowledge for creating API, database, and storage connectors.
  Contains the schema definitions, auth flow patterns, and form field conventions used
  by the Analitiq Stream platform. This skill should be loaded when creating or modifying
  a connector definition (connector.json).
---

# Connector Specification

## Step 1: Determine Connector Type

| Type | When to use | Examples directory |
|------|-------------|-------------------|
| `api` | REST/HTTP API integrations | `examples/api/` |
| `database` | SQL/NoSQL databases | `examples/database/` |
| `other` | File-based, object storage | `examples/other/` |

## Step 2: Read the Matching Example

Read from `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec/examples/{type}/`:

- **`examples/api/`**: `api-key-connector.json`, `basic-auth-connector.json`, `oauth2-authorization-code-connector.json`, `oauth2-client-credentials-connector.json`, `jwt-connector.json`
- **`examples/database/`**: `postgresql-connector.json`, `mysql-connector.json`
- **`examples/other/`**: `s3-connector.json`, `sftp-connector.json`

## Step 3: Read the Detailed Specification

- All types: `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec/spec-common-attributes.md`
- API auth flows: `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec/spec-auth-flows.md`
- Database/other: `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec/spec-form-based.md`

## Step 4: Build the Connector JSON

---

## Common Fields (all connector types)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `connector_id` | UUID string | yes | Unique identifier |
| `connector_name` | string | yes | Display name (e.g. "Xero", "PostgreSQL") |
| `connector_type` | `"api"` / `"database"` / `"other"` | yes | Determines which fields and auth types are valid |
| `connector_descr` | string | no | Human-readable description |
| `connector_group_id` | UUID string | yes | Groups related connectors |
| `slug` | string | yes | URL-safe identifier (lowercase, hyphens) |
| `form_fields` | array | yes | UI form definition (see Form Fields section) |
| `auth` | object | yes | Authentication config — shape depends on `auth.type` |
| `connector_image` | string | no | Logo/image URL |
| `api_doc_url` | string | no | Link to API documentation |

---

## API Connector Fields (`connector_type: "api"`)

These fields are ONLY valid on API connectors and define the runtime behavior:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_url` | string | yes | Base URL for all API data requests. Supports `${placeholder}` for tenant subdomains (e.g. `https://${site}.example.com/api/v1/`) |
| `headers` | object | yes | Headers sent with EVERY API data request. This is where the access token goes. NEVER sent to auth operation URLs |
| `timeout` | integer | no | Request timeout in seconds |
| `requests_per_second` | object | no | Rate limiting: `{ "max_requests": N, "time_window_seconds": N }` |
| `client_required` | boolean | no | Whether the API requires a registered app/client (implies connector-level S3 secret with `client_id`/`client_secret`) |
| `post_auth_steps` | array | no | Steps executed after authentication (tenant selection, token exchange, dynamic host discovery) |
| `host` | string | no | Override host URL |
| `max_connections` | integer | no | Max concurrent connections |

### `headers` — Critical Runtime Field

The `headers` object defines what gets sent with every API data request at runtime. This is where credentials are injected via `${placeholder}`:

```json
"headers": {
  "Authorization": "Bearer ${access_token}",
  "Content-Type": "application/json",
  "xero-tenant-id": "${tenant_id}"
}
```

Key principle: `auth.type` tells the runtime the *flow* (how to get credentials). `headers` tells it *where to put them*. These are orthogonal.

Common patterns:
- Bearer token: `"Authorization": "Bearer ${access_token}"`
- API key in header: `"Authorization": "Bearer ${api_key}"`
- Non-standard: `"X-Shopify-Access-Token": "${access_token}"`, `"Authorization": "Klaviyo-API-Key ${api_key}"`
- Tenant headers: `"xero-tenant-id": "${tenant_id}"`, `"Amazon-Advertising-API-Scope": "${profile_id}"`

### `base_url` — Tenant Patterns

Some APIs embed the tenant into the base URL:
- `https://${site}.chargebee.com/api/v2/`
- `https://${company_domain}.bamboohr.com/api/gateway.php/${company_domain}/v1/`
- `https://${subdomain}.zendesk.com/api/v2/`

The `${placeholder}` resolves from the connection's secrets or DynamoDB attributes at runtime.

---

## Auth Config Shapes

The `auth` object is a discriminated union keyed by `auth.type`. Each type has a DIFFERENT structure. The agent MUST use the correct shape.

### `api_key` — Simplest auth, no token exchange

```json
{ "type": "api_key" }
```
No additional fields. The API key is injected into `headers` via `${placeholder}`.

### `basic_auth` — Username/password encoded as base64

```json
{
  "type": "basic_auth",
  "username_field": "api_key",
  "password_field": ""
}
```
- `username_field`: Name of the form field providing the username (REQUIRED)
- `password_field`: Name of the form field providing the password (REQUIRED, can be empty string)
- Runtime computes `base64(username:password)` and makes it available as `${base64_credentials}`

### `oauth2_authorization_code` — Full OAuth2 with user consent

```json
{
  "type": "oauth2_authorization_code",
  "authorize": {
    "url": "https://login.example.com/authorize?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=read%20write&state=${state}"
  },
  "token_exchange": {
    "url": "https://identity.example.com/token",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded",
    "headers": { "Authorization": "Basic ${basic_auth}" },
    "body": "grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}"
  },
  "refresh": {
    "url": "https://identity.example.com/token",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded",
    "headers": { "Authorization": "Basic ${basic_auth}" },
    "body": "grant_type=refresh_token&refresh_token=${refresh_token}"
  },
  "token_expiry_seconds": 1800
}
```

**Three or four URLs are involved:**
1. `auth.authorize.url` — browser redirect to provider's consent page
2. `auth.token_exchange` — exchanges auth code for tokens (url + method + content_type + body + optional headers)
3. `auth.refresh` — refreshes expired tokens (same structure as token_exchange, optional)
4. `base_url` + root `headers` — API data requests using the `access_token`

**Each operation is a full OAuthEndpoint object:**
| Field | Type | Description |
|-------|------|-------------|
| `url` | string | REQUIRED. Endpoint URL with `${placeholder}` tokens |
| `method` | string | HTTP method (default: POST) |
| `content_type` | string | Content-Type for the request body |
| `body` | string | Request body template with `${placeholder}` tokens |
| `headers` | object | Headers specific to THIS operation (not the root headers) |

**CRITICAL:** `token_exchange` MUST be a full object, not a bare URL string. The runtime needs `url`, `method`, `content_type`, and `body` to construct the token request.

**Token exchange variants:**
- Credentials in headers (Xero, Reddit, QuickBooks): `"headers": { "Authorization": "Basic ${basic_auth}" }`
- Credentials in body (Salesforce, HubSpot): `"body": "...&client_id=${client_id}&client_secret=${client_secret}"`
- Non-standard naming (TikTok): `"body": "{\"app_id\": \"${app_id}\", \"secret\": \"${secret}\", \"auth_code\": \"${code}\"}"`
- PKCE (Twitter/X): adds `code_verifier=${code_verifier}` to body

### `oauth2_client_credentials` — Server-to-server, no user consent

```json
{
  "type": "oauth2_client_credentials",
  "token_exchange": {
    "url": "https://api.example.com/oauth/token",
    "method": "POST",
    "content_type": "application/x-www-form-urlencoded",
    "headers": { "Authorization": "Basic ${basic_auth}" },
    "body": "grant_type=client_credentials"
  },
  "token_expiry_seconds": 3600
}
```

**Two URLs involved:**
1. `auth.token_exchange` — exchanges client_id/secret for access_token
2. `base_url` + root `headers` — API data requests

No `authorize` or `refresh` — runtime re-requests a new token when expired.

**Variants:**
- Credentials in headers: `"headers": { "Authorization": "Basic ${basic_auth}" }` + `"body": "grant_type=client_credentials"`
- Credentials in body: `"body": "grant_type=client_credentials&client_id=${client_id}&client_secret=${client_secret}"`

### `jwt` — Private key signing

```json
{
  "type": "jwt",
  "algorithm": "ES256",
  "claims": {
    "iss": "${issuer_id}",
    "aud": "appstoreconnect-v1"
  },
  "token_expiry_seconds": 1200
}
```
- `algorithm`: REQUIRED — JWT signing algorithm (e.g. `ES256`, `RS256`)
- `claims`: REQUIRED — JWT claims template with `${placeholder}` tokens
- Runtime generates signed JWT from private key stored in S3

### `db` — Database test connection

```json
{
  "type": "db",
  "authorize": {
    "url": "/db_utils",
    "method": "POST",
    "body": "{\"test_connect_only\": true}"
  }
}
```
- `authorize`: REQUIRED — OAuthEndpoint defining the test connection endpoint
- The `authorize.url` is typically `/db_utils` (relative, prefixed with API base)

### `credentials` — Simple credential storage

```json
{ "type": "credentials" }
```
No additional fields. Used for S3, SFTP, and other storage connectors.

---

## Post-Auth Steps

Some APIs require additional steps after authentication (e.g., selecting a tenant/org, discovering a server URL).

```json
"post_auth_steps": [
  {
    "step_order": 1,
    "field_name": "tenant_id",
    "label": "Select Organisation",
    "type": "select",
    "required": true,
    "options_source": {
      "method": "GET",
      "url": "https://api.example.com/tenants",
      "headers": { "Authorization": "Bearer ${access_token}" },
      "items_path": "data.tenants",
      "value_path": "id",
      "label_path": "name"
    }
  }
]
```

Step types:
- `"type": "select"` — user picks from dropdown (e.g., Xero tenant selection)
- `"type": "auto"` — runtime resolves without user interaction (e.g., Linnworks server URL discovery)

Auto steps with `"apply_to": "base_url"` save the result as the connection's base URL (for APIs that return a dynamic server URL).

The `field_name` determines where the result is stored in the connection secret. That name must match the `${placeholder}` used elsewhere (e.g., `${tenant_id}` in headers).

---

## `${placeholder}` Resolution

Every `${placeholder}` in the connector JSON MUST trace to one of these sources:

| Source | Examples | How it gets there |
|--------|----------|-------------------|
| `form_fields` (text) | `${site}`, `${company_domain}` | User enters in UI, stored in DynamoDB |
| `form_fields` (password) | `${api_key}`, `${password}` | User enters in UI, stored in S3 secret |
| OAuth token response | `${access_token}`, `${refresh_token}` | Returned from token_exchange, stored in S3 |
| `post_auth_steps` result | `${tenant_id}`, `${server_url}` | Resolved after auth, stored in S3 secret |
| Connector S3 secret | `${client_id}`, `${client_secret}` | Platform credentials at `api/{connector_id}` |
| Derived values | `${basic_auth}`, `${code}`, `${redirect_uri}`, `${state}` | Computed by runtime |

---

## Database Connector Fields (`connector_type: "database"`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `driver` | string | no | Database driver name: `postgresql`, `mysql`, `mssql`, `oracle`, etc. |
| `enable_ssh` | boolean | no | Whether SSH tunneling is supported (shows SSH fields in UI) |

Database connectors always use `auth.type: "db"` with a test connection `authorize` endpoint.

Standard form fields for databases: `host`, `port`, `database`, `username`, `password`.

---

## Form Fields

`form_fields` defines the UI that users see when creating a connection. Each field:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | REQUIRED — field identifier, used as the key when storing the value |
| `label` | string | REQUIRED — human-readable label shown in UI |
| `type` | enum | REQUIRED — `text`, `password`, `select`, `checkbox`, `hidden`, `textarea`, `oauth2` |
| `required` | boolean | Whether the field must be filled |
| `options` | array | For `select` type: `[{ "value": "...", "label": "..." }]` |
| `default` | string/boolean | Default value |
| `disabled` | boolean | Whether the field is disabled |
| `secret` | boolean | Whether the field is a secret |

Storage rules:
- `text` fields → DynamoDB (connection record)
- `password` fields → S3 secret
- `oauth2` fields → triggers OAuth redirect, tokens stored in S3