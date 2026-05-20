# Reserved (server-managed) fields per entity

Authored documents must **never** contain any of these fields. The
registry stamps them on insert/update. The `reserved-field` Layer 2
validator (see `scripts/validate_pipeline.py`) enforces this.

## Pipeline

- `version`
- `org_id`
- `created_at`
- `updated_at`

`pipeline_id` is **not** reserved — it is an optional authored UUID
(see `identity-and-versioning.md`).

## Stream

- `version`
- `org_id`
- `created_at`
- `updated_at`
- `schema_hash`
- `mapping.assignments_hash` (server-computed, `readOnly`; the schema does not define a top-level `assignments_hash` — `additionalProperties: false` rejects it at Layer 1)
- `source_schema_fingerprint`
- `target_schema_fingerprint`
- `source_schema_id`
- `target_schema_id`
- `source_to_generic`
- `generic_to_destination`
- `type_mapping_assignments_hash`

`stream_id` is **not** reserved — it is an optional authored UUID.
`pipeline_id` is **authored** on streams as the parent pipeline's UUID
cross-reference; it is required.

The legacy mapping fields (`source_to_generic`, `generic_to_destination`,
plus the hash fields above) are server-managed under the new schema.
Authored mapping is `assignments`-only — one entry per destination field.
The registry computes the rest.

## Connection

- `version`
- `org_id`
- `connector_version`
- `auth_state` (the auth lifecycle status block)
- `created_at`
- `updated_at`

`connection_id` is **not** reserved — it is an optional authored UUID.
`connector_id` is **authored** as the connector slug (or UUID) and is
required.

## Database endpoint

- `connector_id`
- `connector_version`
- `connection_id`
- `schema_hash`

`endpoint_id` is **authored** as a slug (`^[a-z0-9][a-z0-9_-]*$`) and is
required — it serves as the catalog key after the endpoint is
materialized.

## Why JSON Schema still has these as `required`

The published JSON Schemas describe the **canonical post-stamped**
document including server fields. The validator strips these from
`required` before running Layer 1 against an authored document, so
authored docs pass without false errors. The inverse (an authored doc
containing a server-managed field) is caught by the `reserved-field`
Layer 2 validator.
