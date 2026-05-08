# HTTP transport idioms

Authoring patterns for `transports` in API connectors.

## Single-origin

The simplest case: one `base_url`, one transport, one set of common headers.

```json
{
  "default_transport": "api",
  "transports": {
    "api": {
      "transport_type": "http",
      "base_url": "https://api.example.com",
      "headers": {
        "Accept": "application/json",
        "Authorization": { "template": "Bearer ${secrets.api_key}" }
      },
      "timeout_seconds": 30,
      "rate_limit": {
        "max_requests": 1000,
        "time_window_seconds": 60
      }
    }
  }
}
```

## Multi-origin

When a provider exposes auth, discovery, and data on different origins
(e.g. Pipedrive: `oauth.pipedrive.com`, `api.pipedrive.com`, and
`{api_domain}.pipedrive.com/api/v1`), define one transport per origin
and factor common headers into `transport_defaults`.

```json
{
  "default_transport": "api",
  "transport_defaults": {
    "transport_type": "http",
    "headers": {
      "Accept": "application/json",
      "Authorization": { "template": "Bearer ${auth.access_token}" }
    }
  },
  "transports": {
    "auth": {
      "base_url": "https://oauth.pipedrive.com",
      "headers": {
        "Authorization": {
          "function": "basic_auth",
          "input": {
            "username": { "ref": "connection.parameters.client_id" },
            "password": { "ref": "secrets.client_secret" }
          }
        }
      }
    },
    "discovery": { "base_url": "https://api.pipedrive.com" },
    "api": {
      "base_url": { "template": "https://${connection.discovered.api_domain}.pipedrive.com/api/v1" }
    }
  }
}
```

The `auth` transport overrides the inherited Bearer `Authorization` with
Basic auth. The `api` transport uses a templated `base_url` whose value
comes from a post-auth output.

## Templated `base_url`

A connector may take a region or subdomain as user input and template
it into `base_url`:

```json
"base_url": { "template": "https://${connection.parameters.region}.example.com" }
```

The matching `region` input must be declared in
`connection_contract.inputs` with `phase: "pre_auth"` so the template is
resolvable before auth.

## Header resolution order

Effective headers per request are built as:

1. Resolved `transport_defaults.headers`.
2. Merge resolved `transports.<ref>.headers`.
3. Remove inherited names listed in operation `headers_remove`.
4. Merge resolved operation `headers`.

Header names match case-insensitively for override and removal.
