# API Connector Research Brief

Research the following API system and answer every question below. Use official documentation as the primary source.

## System
- **Name:** {system_name}
- **Documentation URL:** {url, if provided}

## Questions

### Authentication
1. List ALL authentication methods this API supports (e.g., API key AND OAuth2, or basic auth AND JWT). Use these type names: `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`. Do not pick just one — list every method the API documents.
2. For each auth method: does it require a registered app/client on the target platform? (client_required: true/false)
3. What is the base URL for API data requests? (note any tenant subdomain patterns like `${site}.example.com`)
4. What headers are needed for API data requests? (Authorization format, tenant headers, content-type)

### OAuth Details (if applicable)
5. Authorize URL and required query parameters
6. Token exchange: URL, method, content_type, and body format
7. Refresh: URL, method, content_type, and body format
8. Token expiry duration (seconds)
9. Required scopes

### Post-Auth Steps
10. Does the API require selecting a tenant/org/workspace after authentication?
11. If so: what API call retrieves the options, and what fields map to value/label?

### Rate Limits
12. Requests per time window (max_requests and time_window_seconds)
13. Request timeout (seconds)

### Deprecation
14. Is the API (or any specific API version) deprecated or sunset? If so, what is the recommended replacement?
15. For each auth method found: is that auth method deprecated? (e.g., API key auth being phased out in favor of OAuth2)

### Form Fields
16. What does the user need to provide? (API key, client ID/secret, subdomain, etc.)
17. For each field: name, label, type (text/password/oauth2), required, secret

## Expected Output Format

If the API supports multiple auth methods, return ALL of them in the `auth_methods` array.
The orchestrator will present the options to the user and build a connector for the chosen method.

```json
{
  "source_url": "https://docs.example.com/api/authentication",
  "deprecated": false,
  "auth_methods": [
    {
      "auth_type": "oauth2_authorization_code",
      "deprecated": false,
      "client_required": true,
      "headers": {
        "Authorization": "Bearer ${access_token}",
        "Content-Type": "application/json"
      },
      "auth": {
        "type": "oauth2_authorization_code",
        "authorize": { "url": "..." },
        "token_exchange": { "url": "...", "method": "POST", "content_type": "...", "body": "..." },
        "refresh": { "url": "...", "method": "POST", "content_type": "...", "body": "..." },
        "token_expiry_seconds": 3600
      },
      "form_fields": [],
      "post_auth_steps": []
    },
    {
      "auth_type": "api_key",
      "deprecated": true,
      "client_required": false,
      "headers": {
        "Authorization": "Bearer ${api_key}",
        "Content-Type": "application/json"
      },
      "auth": {
        "type": "api_key"
      },
      "form_fields": [
        { "name": "api_key", "label": "API Key", "type": "password", "required": true, "secret": true }
      ],
      "post_auth_steps": []
    }
  ],
  "base_url": "https://api.example.com/v1/",
  "requests_per_second": { "max_requests": 60, "time_window_seconds": 60 },
  "timeout": 30
}
```

If the API supports only one auth method, still use the `auth_methods` array with a single entry.
