# API Connectors — Auth Flows & Runtime

This document covers API connector auth flows, headers, placeholders, and runtime behavior. For the general connector structure, types, and common attributes, see [spec-common-attributes.md](../connector-scaffolding/spec-common-attributes.md). For database connectors, see [spec-form-based-db.md](../connector-spec-db/spec-form-based-db.md). For storage connectors, see [spec-form-based-storage.md](../connector-spec-storage/spec-form-based-storage.md).

API connectors (`connector_type: "api"`) have these additional root attributes:
- `client_required` - whether the API requires a registered app/client on the target platform to connect and extract data (boolean, default: false). When `true`, the user needs to set up an app on the system (e.g. `client_id`, `client_secret`) that will be used across all connections for this connector for the user
- `base_url` - the base URL for API data requests (nullable for dynamic URL connectors)
- `headers` - headers sent with every API data request, not sent to auth operation URLs (default: `{}`)
- `timeout` - the timeout for each request in seconds (min: 1)
- `requests_per_second` - a map of rate limiting parameters (see below)
- `post_auth_steps` - an array of steps to be taken after authentication (optional)
- `host` - override host URL (optional)
- `max_connections` - max concurrent connections, min: 1 (optional)
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
   "connector_name":"Example API",
   "connector_type":"api",
   "slug":"example-api",
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
   "requests_per_second":{
      "max_requests":60,
      "time_window_seconds":60
   }
}
```
Key rules:
- `auth.type` determines the flow (what the runtime does). Root `headers` determines where credentials go in API data requests. They're independent.
- Every `${placeholder}` in root `headers`, `base_url`, or auth operation fields must be registered in `manifest.json` with a source category.
- Literal header values (e.g. `Accept: application/json`) are static defaults. `${placeholder}` values are resolved from stored parameters or credentials at runtime.
- `form_fields` controls what the user sees: text = plain input, password = masked input, oauth2 = triggers OAuth redirect, select = dropdown.
- `post_auth_steps` types: `"select"` = user picks from dropdown, `"auto"` = runtime resolves without user interaction. Adding `"apply_to": "base_url"` stores the result as the base URL used for API requests.
- Templates like `https://${site}.example.com` in `base_url` are resolved from stored credentials at runtime.

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

Static headers are hardcoded in the connector object. Dynamic headers use `${placeholder}` syntax and are resolved from stored credentials and parameters at runtime.

* non-Bearer header examples: *
- Klaviyo: `"Authorization": "Klaviyo-API-Key ${api_key}"`
- Cin7: `"api-auth-accountid": "${account_id}"` + `"api-auth-applicationkey": "${app_key}"`
- Shopify: `"X-Shopify-Access-Token": "${access_token}"`
- BambooHR: `"Authorization": "Basic ${base64_credentials}"`

### Post Auth Steps

Some connectors require additional steps after authentication before the connector can be used to create a connection.
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

### Credentials

Credentials (API keys, OAuth tokens, passwords, and other secrets) are managed by the platform and resolved into `${placeholder}` tokens at runtime.

How credentials are handled depends on `auth.type`:

**`api_key` / `basic_auth`:**
1. User fills in the `form_fields` on the frontend.
2. No token exchange or refresh needed. Credentials are long-lived until manually revoked.

**`oauth2_authorization_code`:**
1. The platform receives the auth code and exchanges it for tokens via `auth.token_exchange` (url, headers, body).
2. The token response (`access_token`, `refresh_token`, `expires_in`, etc.) is stored by the platform.
3. Token refresh is handled transparently by the platform when `auth.refresh` is present.

**`oauth2_client_credentials`:**
1. The platform exchanges `client_id` + `client_secret` for an `access_token` via `auth.token_exchange` (url, method, content_type, body, and optionally headers).
2. No refresh token — the platform re-requests a new token when the current one expires.
3. `auth.token_exchange` is **required** — a bare `auth.token_url` string is not valid and will not work.

**`jwt`:**
1. The platform generates a signed JWT from stored credentials (private key, issuer ID, key ID).
2. JWT is short-lived and regenerated on expiry.

In all cases, the connector's headers use `${placeholder}` syntax (e.g. `"Authorization": "Bearer ${access_token}"`). Placeholder names must match the stored credential or parmeter attribute names. At runtime, the platform resolves all `${placeholders}` to actual values before making API calls.

### Inline `${placeholder}` Pattern

The `${placeholder}` syntax is used uniformly across all auth operations and root `headers`. All templates are **inline strings** — URLs are URL strings, POST bodies are form-encoded strings, consistent with how `base_url` already works.

**Valid placeholder sources** — every `${placeholder}` must be registered in `manifest.json` with one of these source categories:

| Source | Description | Examples |
|--------|-------------|----------|
| `user_defined` | Values provided by the user via form fields or credential files | `${api_key}`, `${username}`, `${password}`, `${site}` |
| `system_defined` | Values returned by the target system during authentication | `${access_token}`, `${refresh_token}`, `${code}` |
| `post_auth` | Values resolved via post-authentication steps | `${tenant_id}`, `${server_url}`, `${session_token}` |
| `protocol` | OAuth2/auth protocol parameters from app registration or flow setup | `${client_id}`, `${client_secret}`, `${redirect_uri}`, `${state}`, `${code_verifier}` |
| `derived` | Values computed from other placeholders | `${basic_auth}`, `${base64_credentials}`, `${jwt_token}`, `${code_challenge}` |

### Redirect URI

Many APIs — especially those using `client_required: true` — require a `redirect_uri` (or `redirect_url`) to be included in the authorization URL and/or token exchange body. Use the `${redirect_uri}` placeholder in the appropriate `auth.authorize.url` and `auth.token_exchange.body` fields — the platform resolves the value at runtime rather than hardcoding it in the connector JSON.

#### `auth.authorize`

Contains only `url` — the full authorize URL including query parameters, with `${placeholder}` tokens for all dynamic values (`client_id`, `redirect_uri`, `state`, `scopes`, etc.). No headers or body needed (browser redirect).

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

Non-standard naming (TikTok Ads — credentials use `app_id`/`secret` instead of `client_id`/`client_secret`):
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

## Complete Connector Examples

See the JSON example files in `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-api/examples/` for complete connector schemas covering all auth types:

- `api-key-connector.json` — API key auth (15Five)
- `basic-auth-connector.json` — Basic auth (BambooHR)
- `oauth2-authorization-code-connector.json` — OAuth2 with user consent (Xero)
- `oauth2-client-credentials-connector.json` — OAuth2 server-to-server with credentials in headers (PayPal)
- `oauth2-client-credentials-body-connector.json` — OAuth2 server-to-server with credentials in body (Taboola)
- `credentials-post-auth-connector.json` — Credential exchange via post-auth step (CreditSafe)
- `jwt-connector.json` — JWT private key signing (Apple App Store)
- `api-key-dynamic-host-connector.json` — Dynamic host discovery via post-auth steps (Linnworks)
