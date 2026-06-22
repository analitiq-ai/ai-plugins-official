---
name: connector-spec-api
description: API connector authoring vocabulary — auth flows, HTTP transports, pagination, replication, post-auth discovery. Loaded by api-connector-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connector-spec-api

This skill is loaded by `api-connector-creator` when authoring an API
connector. It carries the API-specific vocabulary and examples needed to
populate `transports`, `auth`, `connection_contract`, and
`resource_discovery` for `kind: "api"`, plus the standalone
`type-map-read.json` shipped alongside the connector. API connectors
ship no write map and no package files — those are database-connector
artifacts.

## Required reading (load on demand)

Pick what you need for the auth and pagination styles you're authoring:

- This skill's `spec-auth-flows.md` (for the chosen `auth.type`)
- This skill's `spec-transport.md` (for HTTP transport idioms)
- This skill's `spec-pagination.md` (for endpoint pagination)
- This skill's `spec-replication.md` (for incremental sync)
- `connector-spec-db/spec-type-maps.md` for authoring the standalone
  `type-map-read.json` (same rule shape for API and DB; API ships the
  read direction only)
- The matching example under `examples/<name>/`, which contains both
  `<name>.example.json` (connector body) and a sibling `type-map-read.json`

## What this skill covers

- HTTP transport idioms: single-origin, multi-origin, templated `base_url`.
- All API auth-type templates: `api_key`, `basic_auth`,
  `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt`,
  `credentials`, `aws_iam`, `none`.
- `auth.authorize` / `auth.token_exchange` / `auth.refresh` / `auth.test`
  operation templates.
- Inline function expressions: `basic_auth`, `jwt_sign`, `url_encode`.
- `headers_remove` semantics for inheriting transports.
- `post_auth_outputs` with `options_request` / `discovery_request`.
- Pagination styles (offset / cursor / page / link).
- Replication for incremental sync.

## Endpoint `operations` shape (cross-reference)

Endpoint authoring lives in the `endpoint-creator` agent, but the
operations vocabulary it consumes is API-specific and worth pinning here:

- `operations.read` is a single object with required `request` + `response`
  and optional `params` / `pagination` / `replication`.
- `operations.write` is a **mode-keyed map** — keys are restricted to
  `insert` and `upsert`. Each mode block holds required `request` +
  `input` (`{"schema": <JsonSchemaPropertyNode>}` for one destination
  record) and optional `batching` (`{"max_records": <int ≥ 2>}`),
  `params`, `response`. `upsert` additionally **requires**
  `conflict_keys` — an array of ≥1 top-level field names from
  `input.schema` forming the natural key the upsert matches on; `insert`
  forbids it (the schema pins it to `null`).
- At least one of `read` / `write` must be present; omit the other when
  the resource is one-directional.

## What this skill does NOT cover

- DSN URL templates, bindings, or encoding enums (that's `connector-spec-db`).
- `tls` block (that's `connector-spec-db`).
- Database `resource_discovery` (DB-specific shape).
- Type-map file shape and authoring rules (see
  `connector-spec-db/spec-type-maps.md` — the standalone `type-map-read.json`
  has the same shape for API and DB).
