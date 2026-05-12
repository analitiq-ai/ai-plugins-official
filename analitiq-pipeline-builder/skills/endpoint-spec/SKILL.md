---
name: endpoint-spec
description: Database endpoint authoring vocabulary — database_object identity, columns with native_type and Arrow type, primary_keys. Loaded by private-endpoint-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# endpoint-spec

This skill is loaded by `private-endpoint-creator` when authoring a
database endpoint document conforming to
`https://schemas.analitiq.ai/database-endpoint/latest.json`.

## Required reading (load on demand)

- `spec-database-object.md` — catalog/schema/name/object_type rules; no
  identifier normalization.
- `spec-columns.md` — `name`, `native_type` (required), `arrow_type`
  (required, fully-qualified Apache Arrow canonical type), `nullable`,
  `default`, `comment`, `ordinal_position`.
- At least one of `examples/*.example.json` for the database dialect
  you're authoring.

## Scope

API endpoints come from the connector document, not from here. This
skill is **database-only**. API endpoints in stream `endpoint_ref`s use
`scope: connector` and point at the connector's `definition/endpoints/`.
Database endpoints use `scope: connection` and live under
`connections/{alias}/endpoints/`.

## What this skill covers

- The structural identity of a database object: catalog, schema, name,
  object_type. Identifier strings stored **verbatim** from
  introspection — no case-folding, quoting, or normalization.
- The column shape per table/view/collection.
- Primary keys: optional declared list, must reference existing columns.

## What this skill does NOT cover

- The connection that owns this endpoint — see `connection-spec`.
- Stream-level concerns (filters, replication, pagination, mapping) —
  those belong to `stream-spec`.
- Discovery mechanics (how to query `information_schema` etc.) — that's
  agent logic, encoded in `private-endpoint-creator`.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/database-endpoint/latest.json"`
   (the schema marks this as a `const`-required field).
2. Include `alias` (`[a-z0-9][a-z0-9_-]*`), `database_object`, and a
   non-empty `columns[]`.
3. Preserve identifier strings verbatim from introspection.
4. Pass `python scripts/validate_pipeline.py --entity database_endpoint
   --document <path>` with zero error findings.
