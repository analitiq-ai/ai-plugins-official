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
| `form_fields` | array | no | UI form definition (see Form Fields section) |
| `auth` | object | no | Authentication config — shape depends on `auth.type` |
| `connector_image` | string | no | Logo/image URL |
| `api_doc_url` | string | no | Link to API documentation |

---

## API Connector Fields (`connector_type: "api"`)

These fields are ONLY valid on API connectors and define the runtime behavior:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `base_url` | string | no | Base URL for all API data requests. Supports `${placeholder}` for tenant subdomains (e.g. `https://${site}.example.com/api/v1/`). Nullable for connectors with dynamic URLs resolved via post_auth_steps |
| `headers` | object | no | Headers sent with EVERY API data request. This is where the access token goes. NEVER sent to auth operation URLs. Defaults to `{}` |
| `timeout` | integer | no | Request timeout in seconds (min: 1) |
| `requests_per_second` | object | no | Rate limiting: `{ "max_requests": N, "time_window_seconds": N }` |
| `client_required` | boolean | no | Whether the API requires a registered app/client (implies connector-level S3 secret with `client_id`/`client_secret`). Default: false |
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

## Auth, Post-Auth, Placeholders, Database/Other Fields, Form Fields

For complete specifications on these topics, read the detailed spec files referenced in Step 3 above:

- **Auth config shapes** (discriminated union by `auth.type`): `spec-auth-flows.md` — covers `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`, `db`, `credentials`
- **Post-auth steps** and **`${placeholder}` resolution**: `spec-auth-flows.md`
- **Database/other connector fields** and **form fields**: `spec-form-based.md` and `spec-common-attributes.md`

**Key rules to remember:**
- `auth` is a discriminated union — each `auth.type` has a DIFFERENT shape
- `token_exchange` MUST be a full object (url + method + content_type + body), not a bare URL string
- Every `${placeholder}` must trace to a source: `form_fields`, OAuth token response, `post_auth_steps`, connector S3 secret, or derived values
- Database connectors always use `auth.type: "db"` with a test connection `authorize` endpoint
- `form_fields` type determines storage: `text` → DynamoDB, `password` → S3, `oauth2` → OAuth redirect
