---
name: connector-spec-api
description: API connector authoring vocabulary — auth flows, HTTP transports, pagination, replication, post-auth discovery. Loaded by api-connector-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# connector-spec-api

This skill is loaded by `api-connector-creator` when authoring an API
connector. It carries the API-specific vocabulary and examples needed to
populate `transports`, `auth`, `connection_contract`, `resource_discovery`,
and (rarely) `type_maps` for `kind: "api"`.

## Required reading (load on demand)

Pick what you need for the auth and pagination styles you're authoring:

- This skill's `spec-auth-flows.md` (for the chosen `auth.type`)
- This skill's `spec-transport.md` (for HTTP transport idioms)
- This skill's `spec-pagination.md` (for endpoint pagination)
- This skill's `spec-replication.md` (for incremental sync)
- The matching example under `examples/`

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

## What this skill does NOT cover

- DSN URL templates, bindings, or encoding enums (that's `connector-spec-db`).
- `tls` block (that's `connector-spec-db`).
- Database `resource_discovery` (DB-specific shape).
- Native database type maps.
