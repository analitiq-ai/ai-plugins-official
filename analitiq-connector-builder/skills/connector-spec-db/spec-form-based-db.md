# Database Connectors

Database connectors (`connector_type: "database"`) define connections to SQL and NoSQL databases.

The frontend normalizes all non-`oauth2_authorization_code` auth types to `"form"`, which renders a schema-driven form. Database connectors always use this form flow.

## Additional Attributes

| Attribute | Type | Description |
|---|---|---|
| `driver` | string | Database driver name (e.g. `"postgresql"`, `"mysql"`) |
| `enable_ssh` | boolean | Whether to show SSH tunnel fields in the frontend form |

## Auth Configuration

`auth.type` for database connectors: `"db"`.

### `auth.authorize`

Defines the test connection endpoint. When present, the frontend shows a **Test Connection** button. The user must pass the test before saving.

| Field | Type | Description |
|---|---|---|
| `url` | string | Endpoint path (e.g. `"/db_utils"`). Relative paths are prefixed with `VITE_API_ENDPOINT`; absolute URLs starting with `http` are called directly |
| `method` | string | HTTP method (default: `"POST"`) |
| `body` | string | JSON string with additional key-value pairs to include in the test connection request |

The `body` values are merged into the test payload alongside user-entered form values. Body values override any same-named form fields.

## Example — PostgreSQL

```json
{
  "connector_name": "PostgreSQL",
  "connector_type": "database",
  "slug": "postgresql",
  "driver": "postgresql",
  "enable_ssh": true,
  "auth": {
    "type": "db",
    "authorize": {
      "url": "/db_utils",
      "method": "POST",
      "body": "{\"test_connect_only\": true}"
    }
  },
  "form_fields": [
    { "name": "host", "label": "Host", "type": "text", "required": true },
    { "name": "port", "label": "Port", "type": "text", "required": true },
    { "name": "database", "label": "Database", "type": "text", "required": true },
    { "name": "username", "label": "Username", "type": "text", "required": true },
    { "name": "password", "label": "Password", "type": "password", "required": true, "secret": true }
  ]
}
```
