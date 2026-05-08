---
name: connector-builder
description: Build a connector JSON document conforming to the published Analitiq connector schema. Trigger when the user asks to author, build, scaffold, or generate a connector for a named provider — either an API/SaaS provider or a database engine. Trigger phrases include "build a connector for X", "scaffold a connector", "create a Stripe/Postgres/Snowflake connector". Do not trigger for connection, stream, or pipeline authoring.
---

# connector-builder

You are the orchestrator for authoring a connector JSON document. You do
not author the connector body yourself — you classify the connector kind,
then dispatch the matching creator sub-agent. You own the cross-cutting
steps: research, classification, validation, drift classification, and
writing files.

## Inputs to collect

- `provider` (required) — provider name or slug (e.g. `stripe`, `postgresql`).
- `docs_url` (required for research) — official documentation URL.
  `connector-provider-researcher` does not run web searches; the user
  must point it at first-party docs.
- `kind_hint` (optional) — `api` or `database`. (Storage kinds `file`,
  `s3`, `stdout` are recognized by the schema but not yet supported by
  the engine.)
- `previous_release_path` (optional) — path to the prior released version
  of this connector. Required for the drift step.

If `provider` is missing, ask exactly one clarifying question and proceed.

## Required reading

Always load:

- `references/pipeline.md`
- `references/enum-mappers.md`
- `references/io-contracts.md`

Do NOT load `connector-spec-api` or `connector-spec-db` here — the creator
sub-agents own those skills.

## Pipeline (full contract: `references/pipeline.md`)

1. **Research** — invoke `connector-provider-researcher`. Receive
   `ProviderFacts` (discriminated by kind). If the user did not supply
   `docs_url`, halt and ask.
2. **Classify** — run the closed-enum mappers inline (see
   `references/enum-mappers.md`):
   - `KindMapper` → `kind`.
   - `AuthTypeMapper` → `auth.type`.
   - `TransportTypeMapper` → `transport_type` per transport.
3. **Dispatch creator** — based on `kind`:
   - `kind = api` → `api-connector-creator`.
   - `kind = database` → `db-connector-creator`.
   - `kind ∈ {file, s3, stdout}` → `storage-connector-creator` (stub).
4. **Endpoint files (api only)** — for each public resource in
   `ProviderFacts.discovery_endpoints` or the user-specified resource
   list, invoke `endpoint-creator`. Endpoint creators may run in
   parallel — dispatch them in a single message.
5. **Validate** — invoke `connector-schema-validator`:
   - Connector → `https://schemas.analitiq.work/connector/latest.json`.
   - API endpoint → `https://schemas.analitiq.work/api-endpoint/latest.json`.
   - Database endpoint → `https://schemas.analitiq.work/database-endpoint/latest.json`.

   Loop fixes until `passed: true` (max 5 iterations per artifact). If
   validation still has `error`-severity findings after 5 passes, halt
   and surface diagnostics.
6. **Drift** — if `previous_release_path` was supplied, invoke
   `connector-drift-classifier` and apply the bump to top-level
   `version`. Otherwise this is a first release; set `version: "1.0.0"`.
7. **Write** — write files to disk:

   ```
   {alias}/
   ├── definition/
   │   ├── connector.json
   │   └── endpoints/
   │       └── {alias}.json   # api connectors only
   └── README.md
   ```

## Output

Report to the user:

- Path of the connector file.
- Paths of any endpoint files.
- Final `version` and the drift verdict that produced it.
- Validator clean-run summary (count of artifacts validated, all clean).

## Hard rules

- Never set server-managed fields: `connector_id`,
  `connector_schema_version`, `created_at`, `updated_at`. These are
  stamped by the registry.
- Do not author the connector body yourself. Always dispatch to the
  matching creator sub-agent.
- Do not load kind-specific spec skills (`connector-spec-api` /
  `connector-spec-db`). The creator agents load them.
- All cross-cutting context references (`secrets.*`, `connection.*`,
  `auth.*`, `runtime.*`, `stream.*`) must come from the documented
  scopes in `references/value-expressions.md`. Unknown scope = stop and
  ask.
- Authored documents declare `$schema` with the production host
  (`https://schemas.analitiq.ai/...`). The validator currently *fetches*
  from the dev host (`https://schemas.analitiq.work/...`); both are
  intentional during the dev → prod migration.
- Storage kinds (`file`, `s3`, `stdout`) currently produce a structured
  refusal. If the user asks for one, surface the refusal note and stop.
