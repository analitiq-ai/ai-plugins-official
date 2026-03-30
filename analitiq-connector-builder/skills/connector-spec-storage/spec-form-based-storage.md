# Storage Connectors (Other)

Other connectors (`connector_type: "other"`) cover file-based and object storage systems (S3, SFTP, flat files).

The frontend normalizes all non-`oauth2_authorization_code` auth types to `"form"`, which renders a schema-driven form. Storage connectors always use this form flow.

`auth.type` for other connectors: `"credentials"`.

## Example — S3

```json
{
  "connector_name": "Amazon S3",
  "connector_type": "other",
  "slug": "s3",
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
