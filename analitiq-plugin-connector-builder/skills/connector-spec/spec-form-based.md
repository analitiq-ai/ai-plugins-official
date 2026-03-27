# Form-Based Connectors (Database & Other)

This document covers database and file/storage connector configuration. For the general connector structure, types, and common attributes, see [spec-common-attributes.md](spec-common-attributes.md).

The frontend normalizes all non-`oauth2_authorization_code` auth types to `"form"`, which renders a schema-driven form. Database and other connectors always use this form flow.

## Database Connectors

Database connectors (`connector_type: "database"`) define connections to SQL and NoSQL databases.

### Additional Attributes

| Attribute | Type | Description |
|---|---|---|
| `driver` | string | Database driver name (e.g. `"postgresql"`, `"mysql"`) |
| `enable_ssh` | boolean | Whether to show SSH tunnel fields in the frontend form |

### Auth Configuration

`auth.type` for database connectors: `"db"`.

#### `auth.authorize`

Defines the test connection endpoint. When present, the frontend shows a **Test Connection** button. The user must pass the test before saving.

| Field | Type | Description |
|---|---|---|
| `url` | string | Endpoint path (e.g. `"/db_utils"`). Relative paths are prefixed with `VITE_API_ENDPOINT`; absolute URLs starting with `http` are called directly |
| `method` | string | HTTP method (default: `"POST"`) |
| `body` | string | JSON string merged into the test payload alongside user-entered form values and `connector_id` |

The test payload sent to the endpoint is a flat JSON object: `{ ...formValues, connector_id, ...parsedBody }`. The `body` values are merged last and override any same-named form fields.

### Example — PostgreSQL

```json
{
  "connector_id": "uuid",
  "connector_name": "PostgreSQL",
  "connector_type": "database",
  "slug": "postgresql",
  "connector_group_id": "uuid",
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

## Other Connectors

Other connectors (`connector_type: "other"`) cover file-based and object storage systems (S3, SFTP, flat files).

`auth.type` for other connectors: `"credentials"`.

### Example — S3

```json
{
  "connector_id": "uuid",
  "connector_name": "Amazon S3",
  "connector_type": "other",
  "slug": "s3",
  "connector_group_id": "uuid",
  "auth": {
    "type": "credentials"
  },
  "form_fields": [
    { "name": "bucket", "label": "Bucket Name", "type": "text", "required": true },
    { "name": "region", "label": "AWS Region", "type": "text", "required": true },
    { "name": "access_key_id", "label": "Access Key ID", "type": "text", "required": true },
    { "name": "secret_access_key", "label": "Secret Access Key", "type": "password", "required": true },
    { "name": "prefix", "label": "Key Prefix", "type": "text", "required": false }
  ]
}
```
