---
name: manifest-assembly
disable-model-invocation: true
description: >
  Manifest assembly specification. Defines the manifest.json structure including the placeholder
  registry, endpoint entries, deprecation tagging, and version rules. Used by the wizard
  orchestrator as a final assembly step after all connector-creator and endpoint-creator agents
  have completed.
---

# Manifest Assembly

The `wizard` orchestrator builds `manifest.json` as a **final assembly step** after all sub-agents
complete. No other agent creates or modifies the manifest — this ensures the manifest is built
once with full visibility into `connector.json` and all endpoint files.

## When to Build

- **After Phase 2** (connector creation) for database and storage connectors (no endpoints)
- **After Phase 3** (endpoint creation) for API connectors

## Assembly Steps

1. **Read `connector.json`** — extract all `${placeholder}` tokens from `base_url`, `headers`,
   `auth` operations (`authorize.url`, `token_exchange.url/headers/body`, `refresh.url/headers/body`),
   and `post_auth_steps`.

2. **Categorize each placeholder** by source (see Source Categories below).

3. **Read all endpoint files** in `definition/endpoints/` (API connectors only) — extract any
   `${placeholder}` tokens per endpoint.

4. **Build `manifest.json`** with the complete placeholder registry and endpoint index.

## manifest.json Structure

```json
{
  "connector_name": "<connector_name>",
  "slug": "<slug>",
  "version": "1.0.0",
  "placeholders": [],
  "endpoints": []
}
```

Version starts at `1.0.0`. Do NOT manually bump the version — a GitHub Action bumps it
automatically when a PR is merged, based on PR labels (`version:minor`, `version:patch`,
`version:major`).

## Placeholder Registry

The `placeholders` array is the **single source of truth** for all `${placeholder}` tokens used in
`connector.json` and endpoint files. Every placeholder must be listed here with its source category.

Each entry is an object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Placeholder name (without `${}` wrapper) |
| `source` | string | yes | One of: `user_defined`, `system_defined`, `post_auth`, `protocol`, `derived` |
| `derived_from` | array | only for `derived` | List of placeholder names this value is computed from |

### Source Categories

| Source | Description | Examples |
|--------|-------------|----------|
| `user_defined` | Values provided by the user via form fields or credential files | `api_key`, `username`, `password`, `site`, `company_domain` |
| `system_defined` | Values returned by the target system during authentication | `access_token`, `refresh_token`, `code` |
| `post_auth` | Values resolved via post-authentication steps | `tenant_id`, `server_url`, `session_token`, `account_id` |
| `protocol` | OAuth2/auth protocol parameters from app registration or flow setup | `client_id`, `client_secret`, `redirect_uri`, `state`, `code_verifier` |
| `derived` | Values computed from other placeholders | `basic_auth`, `base64_credentials`, `jwt_token`, `code_challenge` |

### Categorization Rules

Use these rules to determine the correct source for each placeholder:

**`user_defined`** — the placeholder name matches a `form_fields` entry name, OR it is a value
the user provides through credential files (e.g., `api_key`, `username`, `password`, `site`,
`company_domain`, `subdomain`).

**`system_defined`** — the value is returned by the target system's auth server as part of an
authentication response (e.g., `access_token`, `refresh_token`, `code`).

**`post_auth`** — the placeholder name matches a `post_auth_steps[].field_name` value
(e.g., `tenant_id`, `server_url`, `session_token`, `account_id`, `profile_id`).

**`protocol`** — the value is part of OAuth2/auth protocol infrastructure: app registration
outputs (`client_id`, `client_secret`, `app_id`, `app_secret`) or flow parameters
(`redirect_uri`, `state`, `code_verifier`, `scopes`).

**`derived`** — the value is computed from other placeholders. Always include `derived_from`.
Common derived values:
- `basic_auth` — derived from `["client_id", "client_secret"]` (base64-encoded)
- `base64_credentials` — derived from `["username", "password"]` (base64-encoded)
- `jwt_token` — derived from private key and claims (issuer_id, key_id, etc.)
- `code_challenge` — derived from `["code_verifier"]` (SHA256)

### Examples

**OAuth2 Authorization Code** (e.g., Xero):
```json
"placeholders": [
  { "name": "client_id", "source": "protocol" },
  { "name": "client_secret", "source": "protocol" },
  { "name": "redirect_uri", "source": "protocol" },
  { "name": "state", "source": "protocol" },
  { "name": "code", "source": "system_defined" },
  { "name": "access_token", "source": "system_defined" },
  { "name": "refresh_token", "source": "system_defined" },
  { "name": "basic_auth", "source": "derived", "derived_from": ["client_id", "client_secret"] },
  { "name": "tenant_id", "source": "post_auth" }
]
```

**OAuth2 Client Credentials** (e.g., PayPal):
```json
"placeholders": [
  { "name": "client_id", "source": "protocol" },
  { "name": "client_secret", "source": "protocol" },
  { "name": "basic_auth", "source": "derived", "derived_from": ["client_id", "client_secret"] },
  { "name": "access_token", "source": "system_defined" }
]
```

**API Key** (e.g., 15Five):
```json
"placeholders": [
  { "name": "api_key", "source": "user_defined" }
]
```

**Basic Auth with tenant subdomain** (e.g., BambooHR):
```json
"placeholders": [
  { "name": "company_domain", "source": "user_defined" },
  { "name": "base64_credentials", "source": "derived", "derived_from": ["username", "password"] }
]
```

**Dynamic host with post-auth** (e.g., Linnworks):
```json
"placeholders": [
  { "name": "app_id", "source": "user_defined" },
  { "name": "app_secret", "source": "user_defined" },
  { "name": "install_token", "source": "user_defined" },
  { "name": "session_token", "source": "post_auth" },
  { "name": "server_url", "source": "post_auth" }
]
```

**Database and storage connectors** — empty array (no `${placeholder}` substitution):
```json
"placeholders": []
```

## Endpoint Entries

Each endpoint in the `endpoints` array:

```json
{
  "endpoint": "/v1/transfers",
  "method": "GET",
  "version": 1,
  "file": "definition/endpoints/transfers.json",
  "placeholders": []
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint` | string | yes | API endpoint path |
| `method` | string | yes | HTTP method |
| `version` | integer | yes | Schema version (starts at 1) |
| `file` | string | yes | Path to the endpoint JSON file relative to connector root |
| `placeholders` | array | yes | Placeholder tokens used in this endpoint (same format as connector-level) |
| `deprecated` | boolean | no | Only add when `true` — omit entirely for non-deprecated endpoints |

Database and storage connectors have an empty `endpoints` array — they do not have pre-defined
endpoints.

## Deprecation Tagging

If the connector is deprecated, add `"deprecated": true` at the manifest root:

```json
{
  "connector_name": "<connector_name>",
  "slug": "<slug>",
  "version": "1.0.0",
  "deprecated": true,
  "placeholders": [],
  "endpoints": []
}
```

Individual endpoints can be tagged independently:

```json
{
  "endpoint": "/v1/old-resource",
  "method": "GET",
  "version": 1,
  "file": "definition/endpoints/old-resource.json",
  "placeholders": [],
  "deprecated": true
}
```

Only add `"deprecated": true` when applicable. Omit the field entirely for non-deprecated
connectors and endpoints — do not set it to `false`.