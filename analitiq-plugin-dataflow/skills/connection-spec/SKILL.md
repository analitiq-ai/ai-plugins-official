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

Save to `connections/{alias}/.secrets/connection.json`. Format is a flat JSON object:

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

## HTML Credential Form

Instead of collecting credentials via chat, the agent generates a self-contained HTML form that the
user fills in through their browser. The form splits submitted values into the correct output files
based on each field's attributes.

### Output Location

Generated form: `connections/{alias}/credential-form.html`

### Field Splitting Rules

When processing the connector's `form_fields`, each submitted value is routed as follows:

| Condition | Destination |
|---|---|
| `name === "host"` | Top-level `host` field in `connection.json` |
| `secret === true` | `connections/{alias}/.secrets/connection.json` |
| `type === "oauth2"` | Skipped — handled by OAuth2 flow, not rendered as an input |
| Everything else | `parameters` dict in `connection.json` |

Secret fields that are referenced in the connector's `headers` or `parameters` templates (e.g.
`password` in a database connector) must also appear in `connection.json` `parameters` as
`${field_name}` placeholders. The actual values live only in `.secrets/connection.json`.

### Generating the Form — Non-OAuth Connectors

Read the connector's `form_fields` array and build the HTML dynamically:

1. **For each field**, render an input element:
   - `type: "text"` → `<input type="text">`
   - `type: "password"` → `<input type="password">`
   - `type: "select"` → `<select>` (populate options if available)
   - `type: "oauth2"` → skip entirely
   - `required: true` → add HTML `required` attribute + asterisk in label
   - `default` value → set as the input's `value` attribute

2. **Build a `FIELD_META` JS array** from the same `form_fields`:
   ```js
   var FIELD_META = [
     { "name": "host", "secret": false },
     { "name": "port", "secret": false },
     { "name": "password", "secret": true }
   ];
   ```

3. **On form submit**, the JS splits values into three groups using `FIELD_META`:
   - `host` → stored in `data-host` attribute on `#output`
   - Secret fields → JSON in `data-secrets` attribute
   - Non-secret, non-host fields → JSON in `data-parameters` attribute
   - Set `data-complete="true"` to signal the form has been submitted

4. **Include a security reminder** appropriate to the auth type (see Credential Security Reminders).

### Generating the Form — OAuth2 Connectors

OAuth2 forms have a multi-step layout:

**Step 1 — Connection parameters:**
- Render a `client_id` text input (always required — needed to build the authorize URL)
- Render any additional non-oauth2 `form_fields`
- "Next: Authorize" button

**Step 2 — Authorize:**
- JS builds the authorize URL by replacing `${client_id}`, `${redirect_uri}`, and `${state}` in
  the connector's `auth.authorize.url` template
- Redirect URI: `https://app.analitiq.io/oauth/callback`
- State: generated via `crypto.randomUUID()`
- Render a "Connect to {connector_name}" link/button that opens the built URL in a new tab

**Step 3 — Authorization code:**
- Text input for the user to paste the `code` parameter from the callback URL
- "Complete Connection" button
- On submit: store `data-code`, `data-client-id`, `data-parameters`, `data-complete` on `#output`

After the form is submitted, the agent uses the authorization code to perform the token exchange
via the connector's `auth.token_exchange` configuration.

### Reading Form Output

Open the generated form via Playwright MCP tools (`browser_navigate` to the local file path). If
Playwright is not available, instruct the user to open the file in their browser.

After the user submits, read the `data-*` attributes from the `#output` element:

**Non-OAuth forms:**
- `data-host` — value for top-level `host` (empty string if not applicable)
- `data-parameters` — JSON string of non-secret, non-host field values
- `data-secrets` — JSON string of secret field values
- `data-complete` — `"true"` when form has been submitted

**OAuth2 forms:**
- `data-code` — authorization code from the callback URL
- `data-client-id` — the client ID entered by the user
- `data-parameters` — JSON string of additional parameter values
- `data-complete` — `"true"` when form has been submitted

### Form Lifecycle

1. **Generate** the form at `connections/{alias}/credential-form.html`
2. **Open** it for the user (Playwright or manual)
3. **Read** form output after submission
4. **Save** connection.json and .secrets/connection.json from the collected values
5. **Test** credentials by making a test request (non-OAuth only):
   - API connectors: simple GET to `base_url` with resolved headers
   - Database connectors: test connection using the connector's `auth.authorize` config
   - Storage connectors: list/head operation against the bucket/path
6. **Delete** `credential-form.html` after:
   - Non-OAuth: credentials are tested and working
   - OAuth2: tokens are successfully obtained (no testing needed)
7. If testing fails, keep the form so the user can re-open and correct values
