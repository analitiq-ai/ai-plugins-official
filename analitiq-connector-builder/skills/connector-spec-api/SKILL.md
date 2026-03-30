---
name: connector-spec-api
disable-model-invocation: true
description: >
  API connector specification knowledge. Contains auth flow patterns, header conventions,
  placeholder resolution, and API connector examples. Load when creating or modifying
  an API connector definition (connector.json).
---

# API Connector Specification

## Supporting Files

- [spec-auth-flows.md](spec-auth-flows.md) — detailed auth flow patterns per auth type
- `examples/` — complete connector.json examples by auth type (api-key, basic-auth, oauth2, jwt, credentials-post)

## Step 1: Read the Matching Example

Read from `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-api/examples/` — pick the example matching the auth type:

- `api-key-connector.json` — API key auth (15Five)
- `api-key-dynamic-host-connector.json` — Dynamic host discovery via post-auth steps (Linnworks)
- `basic-auth-connector.json` — Basic auth (BambooHR)
- `credentials-post-auth-connector.json` — Credential exchange via post-auth step (CreditSafe)
- `jwt-connector.json` — JWT private key signing (Apple App Store)
- `oauth2-authorization-code-connector.json` — OAuth2 with user consent (Xero)
- `oauth2-client-credentials-connector.json` — OAuth2 server-to-server with credentials in headers (PayPal)
- `oauth2-client-credentials-body-connector.json` — OAuth2 server-to-server with credentials in body (Taboola)

## Step 2: Read the Detailed Specification

Read `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-api/spec-auth-flows.md` for the full API connector schema including:
- Auth flow patterns (api_key, basic_auth, oauth2_authorization_code, oauth2_client_credentials, jwt)
- Header conventions and tenant-specific headers
- Placeholder resolution rules
- Post-auth steps configuration
- Credentials storage and runtime behavior
- Token exchange and refresh patterns

## Step 3: Build the Connector JSON

---

## API Connector Fields (`connector_type: "api"`)

These fields are ONLY valid on API connectors and define the runtime behavior:

| Field | Type | Required | Description                                                                                                                                                                                              |
|-------|------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `base_url` | string | no | Base URL for all API data requests. Supports `${placeholder}` for tenant subdomains (e.g. `https://${site}.example.com/api/v1/`). Nullable for connectors with dynamic URLs resolved via post_auth_steps |
| `headers` | object | no | Headers sent with EVERY API data request. This is where the access token goes. NEVER sent to auth operation URLs. Defaults to `{}`                                                                       |
| `timeout` | integer | no | Request timeout in seconds (min: 1)                                                                                                                                                                      |
| `requests_per_second` | object | no | Rate limiting: `{ "max_requests": N, "time_window_seconds": N }`                                                                                                                                         |
| `client_required` | boolean | no | Whether the API requires a registered app/client (implies user must create an app on the service with `client_id`/`client_secret`). Default: false                                                       |
| `post_auth_steps` | array | no | Steps executed after authentication (tenant selection, token exchange, dynamic host discovery)                                                                                                           |
| `host` | string | no | Override host URL                                                                                                                                                                                        |
| `max_connections` | integer | no | Max concurrent connections                                                                                                                                                                               |

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

The `${placeholder}` resolves from stored connection credentials at runtime.

---

## Auth Configuration

`auth` is a discriminated union — each `auth.type` has a DIFFERENT shape:

- `api_key` / `basic_auth` / `jwt` — no auth operations, credentials injected directly into root `headers`
- `oauth2_authorization_code` — has `authorize`, `token_exchange`, `refresh` operations
- `oauth2_client_credentials` — has `token_exchange` operation

**Critical:** `token_exchange` MUST be a full object (url + method + content_type + body), not a bare URL string.

Every `${placeholder}` must be registered in `manifest.json` with a source category (`user_defined`, `system_defined`, `post_auth`, `protocol`, or `derived`). See the `connector-scaffolding` skill for the placeholder registry format.
