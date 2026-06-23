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
          "enum": ["sqlalchemy", "adbc", "flight_sql", "jdbc", "odbc", "mongodb"]
        },
        "adbc_driver_package": {
          "type": "string",
          "description": "First-class ADBC driver wheel when one exists (e.g. 'adbc-driver-postgresql'); absent when the system has no production ADBC driver. Drives step 1 of the driver-selection decision order."
        },
        "flight_sql_endpoint": {
          "type": "boolean",
          "description": "True when the server exposes an Arrow Flight SQL endpoint (step 2 of the decision order — generic adbc-driver-flightsql)."
        },
        "bulk_load_protocol": {
          "type": "string",
          "description": "The system's native bulk-load path when no ADBC driver exists (e.g. 'LOAD DATA LOCAL INFILE', 'COPY FROM stdin BINARY', 'fast_executemany'). Drives step 3 — async SQLAlchemy transport with the bulk path implemented in the connector class."
        },
        "async_sqlalchemy_driver": {
          "type": "string",
          "description": "The async DBAPI for the SQLAlchemy transport (e.g. 'postgresql+asyncpg', 'mysql+aiomysql'). Sync drivers fail at connect — the engine requires the asyncio extension."
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
              "type-map-coverage",
              "type-map-rule",
              "type-map-write-coverage",
              "endpoint-annotations"
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
              "type-map-rule-added", "type-map-rule-removed",
              "type-map-rule-reordered", "type-map-canonical-changed",
              "bug-fix", "doc-fix", "tuning"
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
  "required": ["connector", "type_map_read"],
  "properties": {
    "connector": {
      "anyOf": [
        { "type": "object", "description": "Assembled connector body, ready for validation against https://schemas.analitiq.ai/connector/latest.json." },
        { "type": "null", "description": "Returned by stub agents (e.g. storage-connector-creator) that decline to author." }
      ]
    },
    "type_map_read": {
      "anyOf": [
        {
          "type": "array",
          "minItems": 1,
          "description": "On-disk shape of the standalone type-map-read.json (native → Arrow): a top-level, non-empty array of {match, native, canonical} rule objects where `native` is the matcher (regex patterns authored UPPERCASE) and `canonical` is the rendered Arrow type (may carry ${name} substitutions backed by named captures in `native`). Written by the orchestrator to {connector_id}/definition/type-map-read.json and validated against https://schemas.analitiq.ai/type-map-read/latest.json.",
          "items": {
            "type": "object",
            "required": ["match", "native", "canonical"],
            "additionalProperties": false,
            "properties": {
              "match":     { "enum": ["exact", "regex"] },
              "native":    { "type": "string", "minLength": 1 },
              "canonical": { "type": "string", "minLength": 1 }
            }
          }
        },
        { "type": "null", "description": "Returned by stub agents that decline to author." }
      ]
    },
    "type_map_write": {
      "anyOf": [
        {
          "type": "array",
          "minItems": 1,
          "description": "On-disk shape of the standalone type-map-write.json (Arrow → native DDL render rules). REQUIRED for kind=database; MUST be null for kind=api. Same rule shape but the direction inverts: `canonical` is the matcher (regex with ECMA named captures for parameterized types) and `native` is the rendered DDL (may carry ${name} substitutions backed by captures in `canonical`). Must cover the full canonical vocabulary; deliberate gaps are allowed only when the dialect overrides render_column_type for that family. Written to {connector_id}/definition/type-map-write.json and validated against https://schemas.analitiq.ai/type-map-write/latest.json (full Layer 1 + Layer 2; direction derived from the filename).",
          "items": {
            "type": "object",
            "required": ["match", "native", "canonical"],
            "additionalProperties": false,
            "properties": {
              "match":     { "enum": ["exact", "regex"] },
              "native":    { "type": "string", "minLength": 1 },
              "canonical": { "type": "string", "minLength": 1 }
            }
          }
        },
        { "type": "null", "description": "kind=api connectors and stub agents return null — the write direction is a database-package concept." }
      ]
    },
    "package_files": {
      "anyOf": [
        {
          "type": "object",
          "required": ["connector_py", "init_py", "requirements_txt", "pyproject_toml"],
          "additionalProperties": false,
          "description": "Python package files for kind=database connectors (the connector root IS the package). MUST be null for kind=api. Written by the orchestrator to {connector_id}/connector.py, __init__.py, requirements.txt, pyproject.toml. Contents follow the connector-package contract in connector-spec-db/spec-connector-package.md; enforcement (wheel build, entry points) is registry CI's job, not the schema validator's.",
          "properties": {
            "connector_py":     { "type": "string", "minLength": 1, "description": "{Name}Dialect(SqlDialect) + {Name}Connector(GenericSQLConnector); CDK imports only." },
            "init_py":          { "type": "string", "minLength": 1, "description": "Re-exports the connector + dialect classes." },
            "requirements_txt": { "type": "string", "minLength": 1, "description": "THIS connector's driver(s) only — async DBAPI and/or adbc-driver-{driver} wheel." },
            "pyproject_toml":   { "type": "string", "minLength": 1, "description": "name=analitiq-connector-{connector_id}; dynamic dependencies from requirements.txt; package-dir maps the repo root; entry points named {connector_id} under analitiq.source_connectors AND analitiq.destination_connectors." }
          }
        },
        { "type": "null", "description": "kind=api connectors and stub agents return null — API connectors carry only the definition." }
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
        "required": ["endpoint_id", "document"],
        "properties": {
          "endpoint_id": {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9_-]*$",
            "description": "Stable endpoint identifier; mirrors document.endpoint_id and is used by the orchestrator to derive the on-disk filename."
          },
          "document": {
            "type": "object",
            "description": "One endpoint document body. Must validate against https://schemas.analitiq.ai/api-endpoint/latest.json and carry the same endpoint_id at its top level."
          }
        }
      }
    }
  }
}
```
