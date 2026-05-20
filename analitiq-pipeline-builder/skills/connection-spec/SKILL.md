---
name: connection-spec
description: Connection authoring vocabulary — single `values` envelope, `.secrets/` template workflow, auth type templates. Loaded by connection-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connection-spec

This skill is loaded by `connection-creator` when authoring a connection
document conforming to `https://schemas.analitiq.ai/connection/latest.json`.

## Required reading (load on demand)

- `spec-values.md` — the single `values` envelope; routing per the
  connector's `connection_contract.inputs`; `.secrets/` template
  generation.
- `spec-auth-types.md` — which template to pick per `connector.auth.type`.
- The matching `examples/*.example.json` for the connector's auth type.

## What this skill covers

- Top-level shape: `$schema`, `connection_id`, `connector_id`,
  `display_name`, `description`, `values`, `tags`. `connector_id` is
  the only schema-required field; everything else is optional.
- The single flat `values` envelope (keyed by connection-contract input or
  post-auth-output name). The server routes each entry into the persisted
  parameters / selections / secrets bucket per the connector contract.
- How to derive `values` keys from the connector's
  `connection_contract.inputs` and how to scaffold `.secrets/` templates
  for inputs that hold secrets.

## What this skill does NOT cover

- The connector's `connection_contract` itself — that lives in the
  connector document, authored by the `analitiq-connector-builder` plugin.
- Endpoint discovery — see `endpoint-spec`.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/connection/latest.json"`.
2. Author `connector_id` (the connector slug being instantiated; required).
   `connection_id` is an RFC-4122 UUID — author one the plugin generates,
   or omit it and let the service assign one on ingest.
3. Place every contract input value into the single `values` envelope. For
   inputs whose stored bucket is `secrets`, write a human-readable
   placeholder (e.g. `"<see .secrets/credentials.json>"`) and emit a
   matching `.secrets/credentials.json` template the user fills in.
4. Pass `python scripts/validate_pipeline.py --entity connection
   --document <path>` with zero error findings.
