---
name: connection-spec
description: >
  Connection specification for authenticating and creating user-specific connection files.
  Contains the ConnectionConfig Pydantic model structure, auth flow guidance per connector
  type, secrets management, and credential collection patterns. This skill should be loaded
  when creating or modifying a connection definition.
---

# Connection Specification

## Step 1: Determine Connector Auth Type

Read the connector's `auth.type` to determine the authentication flow:

| `auth.type` | Credential Flow | Connection Type |
|---|---|---|
| `api_key` | Ask user for API key/token | `host` set, no `connection_type` |
| `basic_auth` | Ask user for username + password | `host` set, no `connection_type` |
| `oauth2_authorization_code` | Browser OAuth flow, save token response | `connection_type: "oauth2"`, NO `host` |
| `oauth2_client_credentials` | Ask for client_id/secret, exchange for token | `host` set, no `connection_type` |
| `jwt` | Ask for private key + issuer + key ID | `host` set, no `connection_type` |
| `db` | Ask for host, port, database, user, password | `host` set, no `connection_type` |
| `credentials` | Ask for storage-specific credentials | `host` may or may not be set |

## Step 2: Read the Matching Example

Read from `${CLAUDE_PLUGIN_ROOT}/skills/connection-spec/examples/{type}/`:

- **`examples/api/`**: `api-key-connection.json`, `oauth2-connection.json` (each with `.secrets.json`)
- **`examples/database/`**: `postgresql-connection.json` (with `.secrets.json`)
- **`examples/other/`**: `s3-connection.json` (with `.secrets.json`)

Each example includes both the connection JSON and the matching secrets file.

## Step 3: Build the Connection JSON

### ConnectionConfig Pydantic Model

The connection JSON must conform to this model (`extra="forbid"` — no unknown fields):

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `connection_id` | string | no | null | UUID, generated on create |
| `org_id` | string | no | null | Organization ID |
| `connection_name` | string | YES | — | User-facing name (min 1 char) |
| `connector_id` | UUID string | YES | — | References the parent connector |
| `connector_name` | string | no | null | Denormalized connector display name |
| `status` | `"draft"` / `"active"` | no | `"draft"` | Set `"active"` after successful auth |
| `connection_type` | `"oauth2"` / null | no | null | ONLY set for OAuth connections |
| `host` | string / null | no | null | Base URL (API) or hostname (DB) |
| `parameters` | dict | no | `{}` | Connector-specific params |
| `headers` | dict[str, str] / null | no | null | HTTP headers for API connections |
| `placeholder_check` | object / null | no | null | Credential validation result |

### Validation Rules

- **CRITICAL:** If `connection_type == "oauth2"`, then `host` MUST be null/omitted. The model validator rejects it.
- `connection_name` must be at least 1 character.
- `connector_id` must be a valid UUID string.
- `extra="forbid"` — do not include any fields not listed above.

### Parameters by Connector Type

**API (non-OAuth) — `api_key`, `basic_auth`, `jwt`:**
```json
{
  "host": "https://api.example.com",
  "parameters": {
    "headers": {
      "Authorization": "Bearer ${token}",
      "Accept": "application/json",
      "Content-Type": "application/json"
    }
  }
}
```
The `headers` inside `parameters` come from the connector's root `headers`, with `${placeholder}` tokens intact. Secrets resolve these at runtime.

**API (OAuth) — `oauth2_authorization_code`:**
```json
{
  "connection_type": "oauth2",
  "parameters": {
    "tenant_id": "selected-tenant-id"
  }
}
```
No `host`. The `parameters` holds post-auth-step results (like `tenant_id`). The access token and refresh token live in the secrets file only.

**API (`oauth2_client_credentials`):**
```json
{
  "host": "https://api.example.com",
  "parameters": {
    "headers": {
      "Authorization": "Bearer ${access_token}",
      "Content-Type": "application/json"
    }
  }
}
```
Has `host` because the runtime manages the token exchange. Access token is in secrets.

**Database:**
```json
{
  "host": "db-hostname.example.com",
  "parameters": {
    "database": "dbname",
    "port": "5432",
    "username": "user",
    "password": "${password}",
    "ssl_mode": "prefer",
    "create_permissions": true
  }
}
```

**S3 / Other:**
```json
{
  "parameters": {
    "bucket": "bucket-name",
    "region": "eu-central-1",
    "prefix": "exports/",
    "access_key_id": "${access_key_id}",
    "secret_access_key": "${secret_access_key}"
  }
}
```

## Step 4: Create the Secrets File

Save to `.secrets/{connection_id}.json` at the project root. Format is a flat JSON object:

**API key / basic auth:**
```json
{ "token": "actual-value" }
```

**OAuth (full token response):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "abc123...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "tenant_id": "abc-123"
}
```

**Database:**
```json
{ "password": "actual-password" }
```

**S3:**
```json
{
  "access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

## Credential Security Reminders

Always remind the user:

- **API keys:** Create a dedicated key for this integration, not a personal or admin key. Use scoped/read-only keys where the platform supports it.
- **Database:** Create a dedicated database user with minimum required permissions (SELECT for source, SELECT+INSERT+UPDATE+DELETE for destination). Never use root/admin.
- **OAuth:** When `client_required: true`, the user must register a dedicated OAuth application. Guide them through the specific platform's developer portal.
- **S3/AWS:** Create a dedicated IAM user with a policy scoped to only the required bucket. Never use root credentials.
- **SFTP:** Create a dedicated SFTP user restricted to the required directory.

## OAuth Client App Registration

When a connector has `client_required: true`, the user must register an app first. Provide platform-specific instructions:

1. Look up the developer portal URL from the connector's `api_doc_url` or search online
2. Tell the user to create a new OAuth application
3. Set redirect URI to: `https://app.analitiq.io/oauth/callback`
4. Extract required scopes from the `auth.authorize.url` scope parameter
5. Ask the user for the resulting Client ID and Client Secret

## PlaceholderCheck

After building the connection, optionally include a `placeholder_check`:

```json
{
  "placeholder_check": {
    "valid": true,
    "missing_keys": [],
    "extra_keys": [],
    "notes": null
  }
}
```

Set `valid: false` if any required `${placeholder}` from the connector's headers/base_url cannot be satisfied by the secrets file keys. List the missing ones in `missing_keys`.
