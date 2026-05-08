# I/O contracts

Pin every I/O between phases and sub-agents as a JSON Schema fragment.

## ProviderFacts (discriminated union by kind)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["provider", "kind"],
  "properties": {
    "provider": { "type": "string" },
    "kind": { "type": "string", "enum": ["api", "database"] },
    "notes": { "type": "string" }
  },
  "oneOf": [
    {
      "properties": {
        "kind": { "const": "api" },
        "auth_model": {
          "type": "object",
          "required": ["family"],
          "properties": {
            "family": {
              "type": "string",
              "enum": [
                "api_key", "basic_auth", "oauth2_authorization_code",
                "oauth2_client_credentials", "jwt",
                "credentials", "aws_iam", "none"
              ]
            },
            "scopes": { "type": "array", "items": { "type": "string" } },
            "redirect_required": { "type": "boolean" },
            "refresh_supported": { "type": "boolean" }
          }
        },
        "base_urls": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "url_or_template"],
            "properties": {
              "name": { "type": "string" },
              "url_or_template": { "type": "string" },
              "depends_on": { "type": "array", "items": { "type": "string" } }
            }
          }
        },
        "post_auth_selections": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "key": { "type": "string" },
              "label": { "type": "string" },
              "discovery_endpoint": { "type": "string" }
            }
          }
        },
        "discovery_endpoints": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "purpose": { "type": "string" },
              "method": { "type": "string" },
              "path": { "type": "string" }
            }
          }
        },
        "pagination": {
          "type": "object",
          "properties": {
            "style": { "type": "string", "enum": ["offset", "page", "cursor", "link", "keyset"] },
            "params": { "type": "array", "items": { "type": "string" } }
          }
        },
        "rate_limit": {
          "type": "object",
          "properties": {
            "max_requests": { "type": "integer" },
            "time_window_seconds": { "type": "integer" }
          }
        }
      },
      "required": ["auth_model"]
    },
    {
      "properties": {
        "kind": { "const": "database" },
        "driver": { "type": "string" },
        "transport_family": {
          "type": "string",
          "enum": ["sqlalchemy", "jdbc", "odbc", "mongodb"]
        },
        "dsn": {
          "type": "object",
          "properties": {
            "url_template_example": { "type": "string" },
            "logical_fields": { "type": "array", "items": { "type": "string" } }
          }
        },
        "tls": {
          "type": "object",
          "properties": {
            "supported_modes": { "type": "array", "items": { "type": "string" } }
          }
        },
        "native_types": {
          "type": "array",
          "items": { "type": "string" }
        },
        "default_port": { "type": "integer" }
      },
      "required": ["driver", "transport_family"]
    }
  ]
}
```

## Diagnostics

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["passed", "findings"],
  "properties": {
    "passed": { "type": "boolean" },
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["validator", "severity", "path", "message"],
        "properties": {
          "validator": {
            "type": "string",
            "enum": [
              "json-schema",
              "reserved-field",
              "expression-resolver",
              "phase-resolvability",
              "transport-ref",
              "dsn-binding",
              "auth-shape",
              "tls-consistency",
              "type-map-coverage"
            ]
          },
          "severity": { "type": "string", "enum": ["error", "warning"] },
          "path": { "type": "string", "description": "JSON pointer into the document" },
          "message": { "type": "string" },
          "rule_doc": { "type": "string" }
        }
      }
    }
  }
}
```

## DriftVerdict

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["bump", "previous_version", "next_version", "rationale"],
  "properties": {
    "bump": { "type": "string", "enum": ["patch", "minor", "major", "none"] },
    "previous_version": { "type": "string" },
    "next_version": { "type": "string" },
    "rationale": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["change_path", "category"],
        "properties": {
          "change_path": { "type": "string" },
          "category": {
            "type": "string",
            "enum": [
              "input-removed", "input-renamed", "input-type-changed",
              "input-enum-narrowed", "storage-changed",
              "non-optional-input-added", "auth-shape-changed",
              "discovery-shape-changed", "optional-input-added",
              "optional-output-added", "optional-endpoint-added",
              "type-map-added", "bug-fix", "doc-fix", "tuning"
            ]
          },
          "note": { "type": "string" }
        }
      }
    }
  }
}
```

## CreatorOutput

Returned by `api-connector-creator` and `db-connector-creator`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["connector"],
  "properties": {
    "connector": {
      "anyOf": [
        { "type": "object", "description": "Assembled connector body, ready for validation against https://schemas.analitiq.work/connector/latest.json." },
        { "type": "null", "description": "Returned by stub agents (e.g. storage-connector-creator) that decline to author." }
      ]
    },
    "notes": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Human-readable notes the orchestrator should surface (e.g. fields the creator could not populate from ProviderFacts)."
    }
  }
}
```

## EndpointCreatorOutput

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["endpoint_files"],
  "properties": {
    "endpoint_files": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["alias", "document"],
        "properties": {
          "alias": { "type": "string" },
          "document": {
            "type": "object",
            "description": "One endpoint document body. Must validate against https://schemas.analitiq.work/api-endpoint/latest.json."
          }
        }
      }
    }
  }
}
```
