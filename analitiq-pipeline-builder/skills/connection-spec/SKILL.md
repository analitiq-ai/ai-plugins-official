---
name: connection-spec
disable-model-invocation: true
description: >
  Connection specification for authenticating and creating user-specific connection files.
  Contains the ConnectionConfig Pydantic model structure, auth flow guidance per connector
  type, secrets management, and credential collection patterns. This skill should be loaded
  when creating or modifying a connection definition.
---

# Connection Specification

## Supporting Files

- `examples/api/` — API key and OAuth2 connection + secrets examples
- `examples/database/` — PostgreSQL connection + secrets example
- `examples/other/` — S3 connection + secrets example

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

| `connection_name` | string | YES | — | User-facing name (min 1 char) |
| `connector_slug` | string | YES | — | Connector slug (e.g., `wise`, `postgresql`, `s3`) |
| `status` | `"draft"` / `"active"` | no | `"draft"` | Set `"active"` after successful auth |
| `connection_type` | `"oauth2"` / null | no | null | ONLY set for OAuth connections |
| `host` | string / null | no | null | Base URL (API) or hostname (DB) |
| `parameters` | dict | no | `{}` | Connector-specific params |
| `headers` | dict[str, str] / null | no | null | HTTP headers for API connections |
| `placeholder_check` | object / null | no | null | Credential validation result |

### Validation Rules

- **CRITICAL:** If `connection_type == "oauth2"`, then `host` MUST be null/omitted. The model validator rejects it.
- `connection_name` must be at least 1 character.
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
    "ssl_mode": "encrypt",
    "create_permissions": true
  }
}
```

### SSL Mode — Canonical Values

Database connectors may define native SSL mode values in their `form_fields` (e.g., PostgreSQL
uses `require`, `verify-full`, `prefer`; MySQL uses `REQUIRED`, `PREFERRED`, `DISABLED`). The
connection-creator agent must map these to canonical values before writing the connection JSON:

| Canonical | Meaning | Native examples |
|-----------|---------|-----------------|
| `none` | No encryption | `disable`, `DISABLED`, `false` |
| `encrypt` | Require encrypted connection | `require`, `REQUIRED`, `true` |
| `verify` | Encrypt + verify server certificate | `verify-ca`, `verify-full`, `VERIFY_CA`, `VERIFY_IDENTITY` |
| `prefer` | Try encrypt, fallback to none at runtime | `prefer`, `PREFERRED`, `allow` |

The connector's `form_fields` keep their native values for display. The connection JSON
`parameters.ssl_mode` always uses one of the four canonical values.

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

Save to `connections/{alias}/.secrets/credentials.json`. Format is a flat JSON object:

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

## OAuth2 Client Prerequisites

Before generating an OAuth2 credential form, the user must register a client application with the
API provider and save the credentials locally.

### Step 1: Check for `.secrets/client.json`

Check whether `connections/{alias}/.secrets/client.json` exists. You may check file existence
(e.g. `test -f` or `ls`), but NEVER read the file content.

### Step 2: If `client.json` does NOT exist

1. Create a template at `connections/{alias}/secrets-templates/client.json`:
   ```json
   {
     "client_id": "YOUR_CLIENT_ID",
     "client_secret": "YOUR_CLIENT_SECRET"
   }
   ```
2. Instruct the user to:
   - Go to the API provider's developer portal (look up from `api_doc_url` or search online)
   - Create a new OAuth application
   - Set redirect URI to: `https://app.analitiq.io/oauth/callback`
   - Note the required scopes (extract from `auth.authorize.url` scope parameter)
   - Copy the template to `.secrets/client.json` and replace the placeholder values with
     the real Client ID and Client Secret
3. Wait for the user to confirm they have saved `.secrets/client.json`
4. Re-check that the file now exists before proceeding

### Step 3: Collect parameters for the authorize URL

Once `client.json` exists, ask the user for:
- **Client ID** — needed to construct the authorize URL (the agent cannot read `.secrets/client.json`)
- Any additional non-oauth2 `form_fields` required before authorization

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

## Credential Collection

Collect credentials through a combination of interview and secrets templates:

1. **Non-sensitive fields** — interview the user directly (host, port, database name, bucket, region, etc.)
2. **Sensitive fields** — create a `.secrets/` template for the user to fill in manually

### Secrets Template

Create `connections/{alias}/.secrets/credentials.json` with placeholder values matching the
connector's secret `form_fields`:

**API key / basic auth:**
```json
{ "token": "REPLACE_WITH_YOUR_API_KEY" }
```

**Database:**
```json
{ "password": "REPLACE_WITH_YOUR_PASSWORD" }
```

**S3:**
```json
{
  "access_key_id": "REPLACE_WITH_ACCESS_KEY_ID",
  "secret_access_key": "REPLACE_WITH_SECRET_ACCESS_KEY"
}
```

Instruct the user to edit the template and replace placeholder values with their actual
credentials before proceeding.

### Field Routing

When processing the connector's `form_fields`, route each value:

| Condition | Destination |
|---|---|
| `name === "host"` | Top-level `host` field in `connection.json` |
| `secret === true` | `.secrets/credentials.json` (template with placeholders) |
| `type === "oauth2"` | Skipped — handled by OAuth2 flow |
| Everything else | `parameters` dict in `connection.json` |

## Output

### Directory Structure

```
connections/{alias}/
├── connection.json
└── .secrets/
    └── connection.json          # Secrets template (user fills in)
```

For database connections, an `endpoints/` directory is created later by the
`private-endpoint-creator` agent after the connection is set up.
