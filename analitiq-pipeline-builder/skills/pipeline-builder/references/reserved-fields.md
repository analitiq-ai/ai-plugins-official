# Reserved (server-managed) fields per entity

Authored documents must **never** contain any of these fields. The
registry stamps them on insert/update. The `reserved-field` Layer 2
validator (see `scripts/validate_pipeline.py`) enforces this.

## Pipeline

- `pipeline_id`
- `version`
- `org_id`
- `created_at`
- `updated_at`

## Stream

- `stream_id`
- `version`
- `org_id`
- `created_at`
- `updated_at`
- `schema_hash`
- `assignments_hash` (top-level and inside `mapping`)
- `source_schema_fingerprint`
- `target_schema_fingerprint`
- `source_schema_id`
- `target_schema_id`
- `source_to_generic`
- `generic_to_destination`
- `type_mapping_assignments_hash`

Note: `pipeline_id` **is** authored on streams (as a base UUID — no
`_v<n>` suffix). It points at the parent pipeline's identity and is
required, not reserved. See `identity-and-versioning.md`.

The legacy mapping fields (`source_to_generic`, `generic_to_destination`,
plus the hash fields above) are server-managed under the new schema.
Authored mapping is `assignments`-only — one entry per destination field.
The registry computes the rest.

## Connection

- `connection_id`
- `version`
- `org_id`
- `connector_id`
- `connector_version`
- `auth_state` (the auth lifecycle status block)
- `created_at`
- `updated_at`

`connector_alias` is **not** reserved — it is authored and immutable.
The registry resolves `connector_alias` → `connector_id` at save time.

## Database endpoint

- `endpoint_id` (the catalog stamps it equal to `alias`)
- `connector_id`
- `connector_version`
- `connection_id`
- `schema_hash`

The endpoint's `alias` is authored and stable — it serves as the
catalog key after the endpoint is materialized.

## Why JSON Schema still has these as `required`

The published JSON Schemas describe the **canonical post-stamped**
document including server fields. The validator strips these from
`required` before running Layer 1 against an authored document, so
authored docs pass without false errors. The inverse (an authored doc
containing a server-managed field) is caught by the `reserved-field`
Layer 2 validator.
