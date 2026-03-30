# Storage Connector Research Brief

Research the following storage/file system and answer every question below. Use official documentation as the primary source.

## System
- **Name:** {system_name}
- **Documentation URL:** {url, if provided}

## Questions

1. What authentication method does this system use? (IAM access keys, service account, username/password, token-based)
2. What are the required connection fields? (bucket, region, path, container, account name, etc.)
3. What are the optional connection fields? (prefix, encryption settings, file format, compression)
4. For each field: is it a secret (e.g. password, access key) or plain text (e.g. bucket name, region)?
5. Are there any special connection caveats? (region-specific endpoints, VPC requirements, etc.)
6. Is this storage system (or the specific API version) deprecated or end-of-life?

## Expected Output Format

```json
{
  "source_url": "https://docs.example.com/auth",
  "deprecated": false,
  "auth_method": "access_keys",
  "form_fields": [
    { "name": "bucket", "label": "Bucket Name", "type": "text", "required": true },
    { "name": "region", "label": "Region", "type": "text", "required": true, "default": "us-east-1" },
    { "name": "access_key_id", "label": "Access Key ID", "type": "text", "required": true },
    { "name": "secret_access_key", "label": "Secret Access Key", "type": "password", "required": true, "secret": true }
  ],
  "notes": "Any special caveats or additional context"
}
```
