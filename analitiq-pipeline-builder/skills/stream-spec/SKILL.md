---
name: stream-spec
description: Stream authoring vocabulary — endpoint refs, source filters/replication/pagination, destinations write modes, mapping assignments, validation rules. Loaded by stream-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# stream-spec

This skill is loaded by `stream-creator` when authoring a stream
document conforming to `https://schemas.analitiq.ai/stream/latest.json`.

## Required reading (load on demand)

- `spec-endpoint-refs.md` — scope=connector vs scope=connection rules.
- `spec-source.md` — selected_columns, filters, replication, database_pagination, primary_keys.
- `spec-destinations.md` — write modes, conflict_keys, execution overrides.
- `spec-mapping.md` — assignments shape; what the registry computes.
- `spec-validation-rules.md` — assignment-level validation.
- `spec-filter-operators.md` — DB vs API operator vocabularies.
- At least one of `examples/*.example.json` for the source/destination kind you're authoring.

## What this skill covers

- Top-level shape: `$schema`, `alias`, `display_name`, `description`,
  `pipeline_id` (base UUID), `source`, `destinations`, `mapping`,
  `status`, `tags`, `documentation_url`.
- The minimal v1 mapping expression vocabulary: `{op: "get", path: "<source field>"}`
  and `{arrow_type, value}` constants.
- The closed source-filter operator vocabularies per endpoint kind.

## What this skill does NOT cover

- The full registry-side type vocabulary expansion. Authored mapping
  declares one assignment per destination field; the registry computes
  `source_to_generic` / `generic_to_destination` / hashes.
- Endpoint bodies. The stream **references** endpoints by ref; it does
  not embed them.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/stream/latest.json"`.
2. Include `alias`, `pipeline_id` (a **base** UUID, no `_v<n>` suffix),
   `source`, and at least one `destinations[]` entry.
3. Omit every reserved field (see
   `../pipeline-builder/references/reserved-fields.md`). In particular:
   no `assignments_hash`, `source_to_generic`, `generic_to_destination`,
   `type_mapping_assignments_hash`, `schema_hash`, or any
   `*_schema_fingerprint`.
4. Use **versioned** connection IDs in every `endpoint_ref.connection_id`.
5. Pass `python scripts/validate_pipeline.py --entity stream
   --document <path>` with zero error findings.
