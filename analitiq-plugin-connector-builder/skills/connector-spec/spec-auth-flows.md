# API Connectors — Auth Flows & Runtime

This document covers API connector auth flows, headers, placeholders, and runtime behavior. For the general connector structure, types, and common attributes, see [spec-common-attributes.md](spec-common-attributes.md). For form-based connectors (database, file/storage), see [spec-form-based.md](spec-form-based.md).

API connectors (`connector_type: "api"`) have these additional root attributes:
- `client_required` - whether the API requires a registered app/client on the target platform to connect and extract data (boolean, required). When `true`, the connector must have a corresponding S3 secret at `analitiq-secrets-{env}/api/{connector_id}` containing the app/client attributes (e.g. `client_id`, `client_secret`)
- `base_url` - the base URL for API data requests
- `headers` - headers sent with every API data request (not sent to auth operation URLs)
- `timeout` - the timeout for each request in seconds
- `rate_limit` - a map of rate limiting parameters (see below)
- `post_auth_steps` - an array of steps to be taken after authentication (optional)
- `api_doc_url` - URL to the API documentation for reference by AI agents (optional)

Some connectors change base URL after auth (Linnworks returns server URL, Mailchimp returns data center). `post_auth_steps` will need to have:
- `"type": "auto"` - no user interaction, runtime resolves automatically
- `"apply_to": "base_url"` - result updates the connection's base URL

Key principle: `auth.type` tells the runtime the *flow* (how to get credentials). Root `headers` tells it *where to put them* in API data requests. These are orthogonal.

Supported `auth.type` values:

| `auth.type` | Frontend Behavior | Runtime Behavior | Auth operations under `auth` |
|---|---|---|---|
| `api_key` | Show form | inject into header, no refresh | none — only `base_url` + root `headers` |
| `basic_auth` | Show form | base64-encode, no refresh | none — only `base_url` + root `headers` |
| `oauth2_authorization_code` | OAuth redirect | token exchange, auto-refresh | `authorize`, `token_exchange`, `refresh` |
| `oauth2_client_credentials` | Server-to-server token request | re-request on expiry | `token_exchange` |
| `jwt` | Sign JWT from private key | regenerate on expiry | none — JWT generated locally |

### URL / Headers / Body Grouping

Each auth type involves one or more URLs, and **each URL has its own headers and body**. The connector schema reflects this by grouping `url` + `headers` + `body` together as a single operation object under `auth`.

**`api_key` / `basic_auth` / `jwt`** — one URL only:
- `base_url` + root `headers` for API data requests. No separate auth operations. Credentials are injected directly into root `headers` via `${placeholder}`.

**`oauth2_client_credentials`** — two URLs:
- `auth.token_exchange` — exchanges `client_id`/`client_secret` for an `access_token` (own url, headers, body)
- `base_url` + root `headers` — API data requests using the `access_token`

**`oauth2_authorization_code`** — three or four URLs:
- `auth.authorize` — browser redirect to the provider's consent page (own url, no headers/body needed)
- `auth.token_exchange` — exchanges the auth code for tokens (own url, headers, body)
- `auth.refresh` — refreshes expired access tokens (own url, headers, body; url often same as `token_exchange`)
- `base_url` + root `headers` — API data requests using the `access_token`

Each operation object can contain:
| Field | Description |
|-------|-------------|
| `url` | The endpoint URL (inline string, supports `${placeholder}`) |
| `method` | HTTP method (default: `POST`) |
| `content_type` | Content-Type header for the request body |
| `headers` | Dict of headers specific to this operation (e.g. `{"Authorization": "Basic ${basic_auth}"}`) |
| `body` | Inline string body with `${placeholder}` tokens |

Root-level `headers` are only for API data requests — they are never sent to `token_exchange` or `refresh` URLs. Each auth operation carries only its own explicitly defined headers.

```json
{
   "connector_id":"uuid",
   "connector_name":"Example API",
   "connector_type":"api",
   "slug":"example-api",
   "connector_group_id":"uuid",
   "base_url":"https://api.example.com/v1/",
   "auth":{
      "type":"oauth2_authorization_code | oauth2_client_credentials | api_key | basic_auth | jwt",
      "authorize":{
         "url":"https://example.com/oauth/authorize?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=read%20write%20offline_access&state=${state}"
      },
      "token_exchange":{
         "url":"https://example.com/oauth/token",
         "method":"POST",
         "content_type":"application/x-www-form-urlencoded",
         "headers":{ "Authorization":"Basic ${basic_auth}" },
         "body":"grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}"
      },
      "refresh":{
         "url":"https://example.com/oauth/token",
         "method":"POST",
         "content_type":"application/x-www-form-urlencoded",
         "headers":{ "Authorization":"Basic ${basic_auth}" },
         "body":"grant_type=refresh_token&refresh_token=${refresh_token}"
      },
      "token_expiry_seconds":3600
   },
   "headers":{
      "Accept":"application/json",
      "Content-Type":"application/json",
      "Authorization":"Bearer ${access_token}",
      "X-Tenant-Id":"${tenant_id}"
   },
   "form_fields":[
      {
         "name":"oauth2",
         "label":"Connect to Example",
         "type":"oauth2",
         "required":true
      },
      {
         "name":"api_key",
         "label":"API Key",
         "type":"password",
         "required":true
      },
      {
         "name":"site",
         "label":"Site Name",
         "type":"text",
         "required":true
      }
   ],
   "post_auth_steps":[
      {
         "step_order":1,
         "field_name":"tenant_id",
         "label":"Select Organisation",
         "type":"select",
         "required":true,
         "options_source":{
            "method":"GET",
            "url":"https://api.example.com/tenants",
            "headers":{
               "Authorization":"Bearer ${access_token}"
            },
            "items_path":"data.tenants",
            "value_path":"id",
            "label_path":"name"
         }
      }
   ],
   "timeout":30,
   "rate_limit":{
      "max_requests":60,
      "time_window_seconds":60
   }
}
```
Key rules:
- `auth.type` determines the flow (what the runtime does). Root `headers` determines where credentials go in API data requests. They're independent.
- Every `${placeholder}` in root `headers`, `base_url`, or auth operation fields must trace to one of: `form_fields` entry, `post_auth_steps` result, OAuth token response (`access_token`, `refresh_token`), or connector S3 secret (`client_id`, `client_secret`).
- Literal header values (e.g. `Accept: application/json`) are connector-level defaults, same for all users. `${placeholder}` values are resolved per-connection from S3
  secrets.
- `form_fields` controls what the user sees: text = plain input, password = masked + stored in S3, oauth2 = triggers OAuth redirect, select = dropdown.
- `post_auth_steps` types: `"select"` = user picks from dropdown, `"auto"` = runtime resolves without user interaction. Adding `"apply_to": "base_url"` saves the result as the connection's base URL.
- Base URL resolution: `connection.base_url` (if set) wins over `connector.base_url`. Templates like `https://${site}.example.com` are resolved from secrets.

A real connector would only include the fields relevant to its auth type — e.g. an API key connector wouldn't have `authorize`, `token_exchange`, `refresh`, or `post_auth_steps`.

**Important:** `oauth2_client_credentials` and `oauth2_authorization_code` connectors MUST have `auth.token_exchange` (an object with `url`, `method`, `content_type`, `body`, and optionally `headers`). A bare `auth.token_url` string is NOT valid — the runtime does not know how to construct the token request from a URL alone. Always use the full `token_exchange` object.

### Base URL

Some connectors could embed the tenant into the base URL itself.
Examples:
```text
  ┌────────────────┬─────────────────────────────────────────┐
  │   Connector    │            Base URL Pattern             │
  ├────────────────┼─────────────────────────────────────────┤                                                                                                            
  │ Chargebee      │ {site}.chargebee.com                    │
  ├────────────────┼─────────────────────────────────────────┤
  │ Freshsales     │ {domain}.freshsales.io                  │
  ├────────────────┼─────────────────────────────────────────┤
  │ Freshdesk      │ {domain}.freshdesk.com                  │
  ├────────────────┼─────────────────────────────────────────┤
  │ Mambu          │ {subdomain}.mambu.com                   │
  ├────────────────┼─────────────────────────────────────────┤
  │ Billomat       │ {billomat_id}.billomat.net              │
  ├────────────────┼─────────────────────────────────────────┤
  │ Centra         │ {store}.centra.com                      │
  ├────────────────┼─────────────────────────────────────────┤
  │ Jira/Atlassian │ {domain}.atlassian.net                  │
  ├────────────────┼─────────────────────────────────────────┤
  │ Qualtrics      │ {datacenter_id}.qualtrics.com           │
  ├────────────────┼─────────────────────────────────────────┤
  │ Mailchimp      │ {dc}.api.mailchimp.com                  │
  ├────────────────┼─────────────────────────────────────────┤
  │ Shopify        │ {shop_name}.myshopify.com               │
  └────────────────┴─────────────────────────────────────────┘
```

### Headers

Root-level `headers` are sent with every API data request. They are **not** sent to auth operation URLs (`token_exchange`, `refresh`) — those carry their own `headers`.

Some connectors may require tenant-specific headers beyond auth tokens.
Examples:
```text
┌──────────────────────────────────┬───────────────────────────────────────┬────────────────────────────────────────────────────────┐                                   
│            Connector             │                Header                 │                        Carries                         │
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Amazon Advertising               │ Amazon-Advertising-API-Scope          │ Advertiser profile ID                                  │                                   
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Bing Ads / Microsoft Advertising │ AccountId, CustomerId, DeveloperToken │ Account ID, customer ID, dev token                     │                                   
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Cin7 (Dear Systems)              │ api-auth-accountid                    │ Cin7 account ID                                        │
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Apple Search Ads                 │ X-AP-Context: orgId={org_id}          │ Organization ID                                        │
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Billomat                         │ X-BillomatApiKey                      │ Account-scoped API key (doubles as tenant identifier)  │
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤                                   
│ Shopify                          │ X-Shopify-Access-Token                │ Store-scoped access token (implicitly tenant-specific) │
├──────────────────────────────────┼───────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Recharge                         │ X-Recharge-Access-Token               │ Merchant-scoped access token                           │
└──────────────────────────────────┴───────────────────────────────────────┴────────────────────────────────────────────────────────┘
```

Connector-level static headers will be hardcoded in the connector object.
Connection-level dynamic headers vary per user/tenant and will be added with placeholder either in connector object, if applies to all connections, or in connection object, if it is connection-specific.

* non-Bearer header examples: *
- Klaviyo: `"Authorization": "Klaviyo-API-Key ${api_key}"`
- Cin7: `"api-auth-accountid": "${account_id}"` + `"api-auth-applicationkey": "${app_key}"`
- Shopify: `"X-Shopify-Access-Token": "${access_token}"`
- BambooHR: `"Authorization": "Basic ${base64_credentials}"`

### Post Auth Steps

When users create a connection to a connector, some connectors require additional steps to be taken before the connection can be used.
Examples:
- Selecting a tenant (e.g. Xero)
- Selecting a client_id (e.g. Salesforce)

If the connector requires additional steps, the connector object should contain a `post_auth_steps` attribute.
The `post_auth_steps` attribute is an array of objects:
```json
{                                                                                                                                                                       
    "post_auth_steps": [                                                                                                                                                 
      {                                                                                                                                                                   
        "step_order": 1,                                                                                                                                                  
        "field_name": "tenant_id",                                                                                                                                        
        "label": "Select Organisation",                                                                                                                                   
        "type": "select",
        "required": true,
        "options_source": {
          "method": "GET",
          "url": "https://api.xero.com/connections",
          "headers": {
            "Authorization": "Bearer ${access_token}"
          },
          "items_path": null,
          "value_path": "tenantId",
          "label_path": "tenantName"
        }
      }
    ]
  }
```

* How It's Visualized (Post-Auth Steps Frontend Flow): *

1. User completes OAuth with Xero. The callback redirects with the connection ID.
2. Frontend calls GET `/connections/{id}?with_connector=true`. The response includes `_resolved_connector.post_auth_steps` — if that array exists and is non-empty, the
   frontend renders the post-auth setup UI.
3. For each step, the frontend calls GET `/connection-options/{connection_id}?step=tenant_id` — this hits the connection-options Lambda, which:
   - Loads the connection to find the `connector_id`
   - Loads the connector's `post_auth_steps`, finds the step where `field_name == "tenant_id"`
   - Fetches the OAuth access_token from S3 (never exposed to the frontend)
   - Calls GET `https://api.xero.com/connections` with the token
   - Returns `[{value: "abc-123", label: "My Company Ltd"}, ...]`
4. The frontend renders this as a dropdown (because type: "select").
5. User picks an organization. Frontend calls PATCH `/connections/{id}` with `{"tenant_id": "abc-123"}`.
6. From then on, `tenant_id` is stored on the S3 with the connection secret and injected as the `xero-tenant-id` header at runtime via the connector's header template "xero-tenant-id":
   "${tenant_id}".

### Credentials

Credentials (API keys, OAuth tokens, passwords, and other secrets) are stored in S3 as JSON objects at `analitiq-secrets-{env}/connections/{client_id}/{connection_id}`.

How credentials reach S3 depends on `auth.type`:

**`api_key` / `basic_auth`:**
1. User fills in the `form_fields` on the frontend.
2. Fields with `type: "password"` are saved to S3. Fields with `type: "text"` are saved to DynamoDB on the connection record.
3. No token exchange or refresh needed. Credentials are long-lived until manually revoked.

**`oauth2_authorization_code`:**
1. `oauth2_callback` Lambda receives the auth code, exchanges it for tokens via `auth.token_exchange` (url, headers, body).
2. The token response (`access_token`, `refresh_token`, `expires_in`, etc.) is saved to S3.
3. Token refresh is handled transparently by the runtime when `auth.refresh` is present.

**`oauth2_client_credentials`:**
1. Runtime exchanges `client_id` + `client_secret` (from S3) for an `access_token` via `auth.token_exchange` (url, method, content_type, body, and optionally headers).
2. No refresh token — runtime re-requests a new token when the current one expires.
3. `auth.token_exchange` is **required** — a bare `auth.token_url` string is not valid and will not work.

**`jwt`:**
1. Runtime generates a signed JWT from credentials stored in S3 (private key, issuer ID, key ID).
2. JWT is short-lived and regenerated on expiry.

In all cases, the connector's headers use `${placeholder}` syntax (e.g. `"Authorization": "Bearer ${access_token}"`). Placeholder names must match the attribute names in the S3 secret. At runtime, the system merges the connector config with the connection's S3 secret, resolving all `${placeholders}` to actual values before making API calls.

### Inline `${placeholder}` Pattern

The `${placeholder}` syntax is used uniformly across all auth operations and root `headers`. All templates are **inline strings** — URLs are URL strings, POST bodies are form-encoded strings, consistent with how `base_url` already works.

**Runtime Context Resolution** — the runtime builds a single context dict by merging (later wins):
1. **Connector S3 secret** — all keys from `api/{connector_id}` (e.g. `client_id`, `client_secret`, `app_id`, `secret`)
2. **Connection S3 secret** — all keys from `connections/{client_id}/{connection_id}` (e.g. `access_token`, `refresh_token`)
3. **Derived values** — `basic_auth` = base64(`client_id:client_secret`) computed when headers contain `${basic_auth}`
4. **Runtime values** — `code`, `redirect_uri`, `state`, `code_verifier` (injected by Lambda/frontend context)

### Redirect URI

Many APIs — especially those using `client_required: true` — require a `redirect_uri` (or `redirect_url`) to be included in the authorization URL and/or token exchange body. When this is the case, add `redirect_uri` as an attribute in the connector's S3 secret at `analitiq-secrets-{env}/api/{connector_id}`, and use the `${redirect_uri}` placeholder in the appropriate `auth.authorize.url` and `auth.token_exchange.body` fields. This way the value is resolved from the secret at runtime rather than hardcoded in the connector JSON.

#### `auth.authorize`

Contains only `url` — the full authorize URL including query parameters, with `${placeholder}` for both S3-sourced values (like `client_id`) and frontend-provided values (`redirect_uri`, `state`). No headers or body needed (browser redirect).

When GET `/connectors/{id}` returns the connector, S3-sourced placeholders are pre-resolved in `_resolved_authorize_url`. Frontend placeholders (`${redirect_uri}`, `${state}`, `${code_challenge}`, `${scopes}`) are left intact for the frontend to fill.

Variations:
| API | `authorize.url` |
|-----|-----------------|
| Xero | `...?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=...&state=${state}` |
| TikTok Social | `...?client_key=${client_key}&response_type=code&scope=${scopes}&redirect_uri=${redirect_uri}&state=${state}` |
| Twitter/X (PKCE) | `...?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=${scopes}&state=${state}&code_challenge=${code_challenge}&code_challenge_method=S256` |
| Zendesk | `https://${subdomain}.zendesk.com/oauth/authorizations/new?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=${scopes}` |

#### `auth.token_exchange`

Groups `url` + `headers` + `body` for the code-to-token exchange. Used by `oauth2_authorization_code` and `oauth2_client_credentials`.

Basic auth variant (Xero, Reddit, QuickBooks, Pinterest) — credentials in headers:
```json
"token_exchange": {
  "url": "https://identity.xero.com/connect/token",
  "method": "POST",
  "content_type": "application/x-www-form-urlencoded",
  "headers": { "Authorization": "Basic ${basic_auth}" },
  "body": "grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}"
}
```

Body-auth variant (Salesforce, HubSpot, Snapchat, Discord) — credentials in body:
```json
"token_exchange": {
  "url": "https://login.salesforce.com/services/oauth2/token",
  "method": "POST",
  "content_type": "application/x-www-form-urlencoded",
  "body": "grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}&client_id=${client_id}&client_secret=${client_secret}"
}
```

Non-standard naming (TikTok Ads — S3 has `app_id`/`secret`):
```json
"token_exchange": {
  "url": "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
  "method": "POST",
  "content_type": "application/json",
  "body": "{\"app_id\": \"${app_id}\", \"secret\": \"${secret}\", \"auth_code\": \"${code}\"}"
}
```

PKCE (Twitter/X):
```json
"token_exchange": {
  "url": "https://api.x.com/2/oauth2/token",
  "method": "POST",
  "content_type": "application/x-www-form-urlencoded",
  "headers": { "Authorization": "Basic ${basic_auth}" },
  "body": "grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}&code_verifier=${code_verifier}"
}
```

#### `auth.refresh`

Groups `url` + `headers` + `body` for token refresh. Same structure as `token_exchange`. Present only when the provider supports refresh tokens.

Basic auth refresh (Xero, QuickBooks):
```json
"refresh": {
  "url": "https://identity.xero.com/connect/token",
  "method": "POST",
  "content_type": "application/x-www-form-urlencoded",
  "headers": { "Authorization": "Basic ${basic_auth}" },
  "body": "grant_type=refresh_token&refresh_token=${refresh_token}"
}
```

Body-auth refresh (Google, Bing, Snapchat):
```json
"refresh": {
  "url": "https://oauth2.googleapis.com/token",
  "method": "POST",
  "content_type": "application/x-www-form-urlencoded",
  "body": "grant_type=refresh_token&refresh_token=${refresh_token}&client_id=${client_id}&client_secret=${client_secret}"
}
```

#### Root `headers` (API data requests)

Sent with every API data request to `base_url`. Never sent to auth operation URLs.
```json
"headers": {
  "Authorization": "Bearer ${access_token}",
  "Content-Type": "application/json",
  "xero-tenant-id": "${tenant_id}"
}
```

## User Interface / Frontend Flow

1. Frontend calls GET `/connectors/{id}` (or gets the connector via a connection). It sees `auth.type: "oauth2_authorization_code"`.
2. The response includes `_resolved_authorize_url` where S3-sourced placeholders (like `${client_id}`) from `auth.authorize.url` are already resolved. Frontend fills in remaining placeholders (`${redirect_uri}`, `${state}`, `${code_challenge}`) and renders a "Connect with ..." button.
3. User clicks the button. Browser redirects to the service provider's auth page.
4. After user authorizes, API service redirects to `oauth2_callback` with an auth code.
5. `oauth2_callback` Lambda uses `auth.token_exchange` (url, headers, body) to exchange the code for tokens, saves them to S3, saves the connection to DynamoDB, and redirects back
   to the frontend with `?id={connection_id}`.
6. If the connector has `post_auth_steps`, the frontend then enters the post-auth flow (as described earlier).

## Runtime

At runtime, when making an API call, the system merges connector-level defaults with connection-level overrides (connection wins on conflict).

**Base URL resolution** (in order):
1. If `connection.base_url` is set, use it (dynamic discovery or user override)
2. Otherwise, resolve `connector.base_url` template by replacing `${placeholders}` with values from the connection's S3 secret

**Header resolution** (for API data requests only):
1. Start with `connector.headers`
2. Overlay any `connection.headers` (connection wins on conflict)
3. Resolve all `${placeholders}` from S3 secrets

**Placeholder sources** (in resolution order):
1. OAuth token response fields (`access_token`, `refresh_token`, `expires_in`)
2. Connection S3 secrets (user-provided via `form_fields`: `api_key`, `site`, `tenant_id`, etc.)
3. `post_auth_steps` results (`server_url`, `session_token`, `division`, etc.)

The name of the parameters in `${placeholders}` must match the attribute name saved in the S3 secret so expansion happens seamlessly.

## Complete Connector Schema Examples

### OAuth2 Authorization Code (Xero):
```json
{
  "base_url": "https://api.xero.com/api.xro/2.0/",
  "auth": {
    "type": "oauth2_authorization_code",
    "authorize": {
      "url": "https://login.xero.com/identity/connect/authorize?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=accounting.transactions%20offline_access&state=${state}"
    },
    "token_exchange": {
      "url": "https://identity.xero.com/connect/token",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "headers": { "Authorization": "Basic ${basic_auth}" },
      "body": "grant_type=authorization_code&code=${code}&redirect_uri=${redirect_uri}"
    },
    "refresh": {
      "url": "https://identity.xero.com/connect/token",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "headers": { "Authorization": "Basic ${basic_auth}" },
      "body": "grant_type=refresh_token&refresh_token=${refresh_token}"
    },
    "token_expiry_seconds": 1800
  },
  "headers": {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer ${access_token}",
    "xero-tenant-id": "${tenant_id}"
  },
  "form_fields": [
    { "name": "oauth2", "label": "Connect to Xero", "type": "oauth2", "required": true }
  ],
  "post_auth_steps": [
    {
      "step_order": 1,
      "field_name": "tenant_id",
      "label": "Select Organisation",
      "type": "select",
      "required": true,
      "options_source": {
        "method": "GET",
        "url": "https://api.xero.com/connections",
        "headers": { "Authorization": "Bearer ${access_token}" },
        "items_path": null,
        "value_path": "tenantId",
        "label_path": "tenantName"
      }
    }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### Basic Auth (BambooHR):
```json
{
  "base_url": "https://${company_domain}.bamboohr.com/api/gateway.php/${company_domain}/v1/",
  "auth": {
    "type": "basic_auth",
    "username_field": "api_key",
    "password_field": ""
  },
  "headers": {
    "Accept": "application/json",
    "Authorization": "Basic ${base64_credentials}"
  },
  "form_fields": [
    { "name": "company_domain", "label": "Company Subdomain", "type": "text", "required": true },
    { "name": "api_key", "label": "API Key", "type": "password", "required": true }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### API Key (15Five):
```json
{
  "base_url": "https://my.15five.com/api/public/",
  "auth": { "type": "api_key" },
  "headers": {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer ${api_key}"
  },
  "form_fields": [
    { "name": "api_key", "label": "API Key", "type": "password", "required": true }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### OAuth2 Client Credentials — Basic Auth (PayPal):
```json
{
  "base_url": "https://api-m.paypal.com/",
  "auth": {
    "type": "oauth2_client_credentials",
    "token_exchange": {
      "url": "https://api-m.paypal.com/v1/oauth2/token",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "headers": { "Authorization": "Basic ${basic_auth}" },
      "body": "grant_type=client_credentials"
    },
    "token_expiry_seconds": 32400
  },
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${access_token}"
  },
  "form_fields": [
    { "name": "client_id", "label": "Client ID", "type": "text", "required": true },
    { "name": "client_secret", "label": "Client Secret", "type": "password", "required": true }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 30, "time_window_seconds": 1 }
}
```

### OAuth2 Client Credentials — Body Auth (Taboola):
```json
{
  "base_url": "https://backstage.taboola.com/backstage/api/1.0/",
  "auth": {
    "type": "oauth2_client_credentials",
    "token_exchange": {
      "url": "https://backstage.taboola.com/backstage/oauth/token",
      "method": "POST",
      "content_type": "application/x-www-form-urlencoded",
      "body": "grant_type=client_credentials&client_id=${client_id}&client_secret=${client_secret}"
    },
    "token_expiry_seconds": 3600
  },
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${access_token}"
  },
  "form_fields": [
    { "name": "client_id", "label": "Client ID", "type": "text", "required": true },
    { "name": "client_secret", "label": "Client Secret", "type": "password", "required": true }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### Credential Exchange via Post-Auth Step (CreditSafe):
```json
{
  "base_url": "https://connect.creditsafe.com/v1/",
  "auth": { "type": "api_key" },
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${auth_token}"
  },
  "form_fields": [
    { "name": "username", "label": "Username", "type": "text", "required": true },
    { "name": "password", "label": "Password", "type": "password", "required": true }
  ],
  "post_auth_steps": [
    {
      "step_order": 1,
      "field_name": "auth_token",
      "type": "auto",
      "token_expiry_seconds": 3600,
      "source": {
        "method": "POST",
        "url": "https://connect.creditsafe.com/v1/authenticate",
        "headers": { "Content-Type": "application/json" },
        "body": {
          "username": "${username}",
          "password": "${password}"
        },
        "value_path": "token"
      }
    }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### JWT (Apple App Store):
```json
{
  "base_url": "https://api.appstoreconnect.apple.com/v1/",
  "auth": {
    "type": "jwt",
    "algorithm": "ES256",
    "token_expiry_seconds": 1200,
    "claims": {
      "iss": "${issuer_id}",
      "aud": "appstoreconnect-v1"
    }
  },
  "headers": {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer ${jwt_token}"
  },
  "form_fields": [
    { "name": "issuer_id", "label": "Issuer ID", "type": "text", "required": true },
    { "name": "key_id", "label": "Key ID", "type": "text", "required": true },
    { "name": "private_key", "label": "Private Key (.p8)", "type": "password", "required": true }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 60, "time_window_seconds": 60 }
}
```

### Dynamic Host Discovery (Linnworks):
```json
{
  "base_url": "${server_url}",
  "auth": { "type": "api_key" },
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "${session_token}"
  },
  "form_fields": [
    { "name": "app_id", "label": "Application ID", "type": "text", "required": true },
    { "name": "app_secret", "label": "Application Secret", "type": "password", "required": true },
    { "name": "install_token", "label": "Installation Token", "type": "password", "required": true }
  ],
  "post_auth_steps": [
    {
      "step_order": 1,
      "field_name": "session_token",
      "type": "auto",
      "source": {
        "method": "POST",
        "url": "https://api.linnworks.net/api/Auth/AuthorizeByApplication",
        "body": {
          "applicationId": "${app_id}",
          "applicationSecret": "${app_secret}",
          "token": "${install_token}"
        },
        "value_path": "Token"
      }
    },
    {
      "step_order": 2,
      "field_name": "server_url",
      "type": "auto",
      "source": "same_response",
      "value_path": "Server",
      "apply_to": "base_url"
    }
  ],
  "timeout": 30,
  "rate_limit": { "max_requests": 150, "time_window_seconds": 60 }
}
```
