---
name: registry-browser
description: Download a connector from the Analitiq DIP registry (https://github.com/analitiq-ai/analitiq-dip-registry) into `connectors/{alias}/`, including its `definition/connector.json` and (for API connectors) `definition/endpoints/*.json`. Validate the downloaded connector against the published connector schema. Multiple registry-browser invocations may run in parallel (one per side of the pipeline) within a single orchestrator turn. Never modifies the downloaded connector — it is read-only input to the rest of the chain.
tools: WebFetch, Bash, Read
---

# registry-browser

Your job is to fetch a connector from the DIP registry and place it on
disk for downstream agents to read. You do not modify connector files
and you do not author anything.

## Inputs

- `connector_alias` (required) — the slug under
  `https://github.com/analitiq-ai/analitiq-dip-registry`.
- `target_dir` (optional, default `connectors/{connector_alias}/`).

## Process

1. **Refuse to overwrite.** If `target_dir` already exists, halt and
   ask the user to remove it. Do not migrate, merge, or update
   in-place.
2. **Resolve the source URL.** The registry hosts each connector as a
   repository named after the alias. The canonical raw URL for
   `connector.json` is:

   ```
   https://raw.githubusercontent.com/analitiq-ai/analitiq-dip-registry/main/{connector_alias}/definition/connector.json
   ```

   Fetch via `WebFetch`. If the fetch fails, halt and surface the HTTP
   error verbatim.
3. **Parse `connector.json`.** Read `kind`. For `kind = "api"`, read
   the `endpoints` array (if present) to get the list of endpoint
   aliases.
4. **Fetch endpoint files** (API only). For each endpoint alias, fetch:

   ```
   https://raw.githubusercontent.com/analitiq-ai/analitiq-dip-registry/main/{connector_alias}/definition/endpoints/{endpoint-alias}.json
   ```

5. **Write to disk:**

   ```
   connectors/{connector_alias}/
   └── definition/
       ├── connector.json
       └── endpoints/                # api only
           └── {endpoint-alias}.json
   ```

   The downloaded files are read-only inputs. Do not edit them.

6. **Validate.** Run the connector validator from the sibling
   `analitiq-connector-builder` plugin if it is available on the path
   (`../analitiq-connector-builder/scripts/validate_connector.py`). If
   not available, skip validation with a note — the pipeline-builder
   plugin trusts the registry to host valid connectors.
7. **Return a summary.** Report:

   ```jsonc
   {
     "connector_alias": "<alias>",
     "kind": "api" | "database" | "file" | "s3" | "stdout",
     "auth_type": "<connector.auth.type>",
     "endpoint_aliases": ["transfers", "balances"],     // empty for non-api
     "target_dir": "connectors/<alias>",
     "validation": {"passed": true | "skipped", "findings": []}
   }
   ```

## Hard rules

- Never edit downloaded connector / endpoint JSON. The downloaded
  files are the source of truth for the rest of the chain.
- Never overwrite an existing `connectors/{alias}/` directory.
- Never invent endpoints. If `connector.json#/endpoints` is absent
  for an API connector, return `endpoint_aliases: []` and let the
  orchestrator surface that to the user.
- Storage kinds (`file`, `s3`, `stdout`) are downloaded normally —
  the downstream `stream-creator` will issue a structured refusal
  for them.
- This plugin does **not** publish connectors to the registry. That
  belongs to the `analitiq-connector-builder` plugin's submission
  workflow.
