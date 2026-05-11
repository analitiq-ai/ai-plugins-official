---
name: connection-spec
description: Connection authoring vocabulary — parameters routing, secret_refs format, selections/discovered, auth type templates. Loaded by connection-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connection-spec

This skill is loaded by `connection-creator` when authoring a connection
document conforming to `https://schemas.analitiq.ai/connection/latest.json`.

## Required reading (load on demand)

- `spec-parameters.md` — routing per the connector's `connection_contract.inputs`.
- `spec-secrets.md` — `secret_refs` format and `.secrets/` template generation.
- `spec-selections-discovered.md` — post-auth output handling.
- `spec-auth-types.md` — which template to pick per `connector.auth.type`.
- The matching `examples/*.example.json` for the connector's auth type.

## What this skill covers

- Top-level shape: `$schema`, `alias`, `connector_alias`, `display_name`,
  `description`, `parameters`, `secret_refs`, `selections`, `discovered`,
  `tags`, `documentation_url`.
- The seven `secret_refs` URI prefixes (`secrets/`, `connections/`,
  `ssm:/`, `arn:aws:secretsmanager:…:secret:…`,
  `arn:aws:ssm:…:parameter/…`, `s3://…`).
- How to derive `parameters` and `secret_refs` keys from the connector's
  `connection_contract.inputs`.

## What this skill does NOT cover

- `auth_state` — server-managed; the plugin never authors it.
- The connector's `connection_contract` itself — that lives in the
  connector document, authored by the `analitiq-connector-builder` plugin.
- Endpoint discovery — see `endpoint-spec`.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/connection/latest.json"`.
2. Include `alias` (`[a-z0-9][a-z0-9_-]*`) and `connector_alias` (the
   slug of the connector being instantiated).
3. Omit every reserved field — especially `connection_id`, `connector_id`,
   `connector_version`, `auth_state` (see
   `../pipeline-builder/references/reserved-fields.md`).
4. Route every contract input declared with `storage: "connection.parameters"`
   into `parameters`, and every input declared with `storage: "secrets"`
   into `secret_refs` (the value is a reference string, never the
   secret value itself).
5. Pass `python scripts/validate_pipeline.py --entity connection
   --document <path>` with zero error findings.
