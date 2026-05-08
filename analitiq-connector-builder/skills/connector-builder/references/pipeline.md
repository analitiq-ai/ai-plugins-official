# Orchestration pipeline

Phase-by-phase contract for the `connector-builder` orchestrator. Loaded
on demand by the orchestrator skill.

## Phases

### 1. Research

Invoke `connector-provider-researcher` with `provider`, optional
`kind_hint`, and the official-docs URL the user supplied. Receive a
`ProviderFacts` JSON object discriminated by `kind`.

**Input:** `provider`, `kind_hint?`, `docs_url`.
**Output:** `ProviderFacts`.
**Failure mode:** if researcher cannot access the docs, halt and ask the
user to fix the URL or pass through manually-supplied facts.

### 2. Classify

Run the closed-enum mappers inline (see `enum-mappers.md`):

- `KindMapper` → `kind` (one of `api`, `database`).
- `AuthTypeMapper` → `auth.type`.
- `TransportTypeMapper` → `transport_type` per transport.

Storage kinds (`file`, `s3`, `stdout`) are accepted by the schema but not
yet supported by the engine. If the user explicitly asked for one,
dispatch to `storage-connector-creator` (which currently returns a
structured refusal); otherwise fail closed and ask.

### 3. Dispatch creator

Based on `kind`:

- `kind = api` → invoke `api-connector-creator` with `ProviderFacts` plus
  classifications.
- `kind = database` → invoke `db-connector-creator` with the same.
- `kind ∈ {file, s3, stdout}` → invoke `storage-connector-creator` (stub).

Receive a `CreatorOutput` JSON object containing the assembled connector
body.

### 4. Endpoint files (api only)

For each public resource in `ProviderFacts.discovery_endpoints` or the
user-specified resource list, invoke `endpoint-creator`. Endpoint creators
may run in parallel — dispatch them in a single message.

Database connectors do not ship endpoint files; their schema/table
combinations are connection-scoped and discovered at runtime via
`resource_discovery`.

### 5. Validate

Invoke `connector-schema-validator` with the connector document and
`schema_url=https://schemas.analitiq.work/connector/latest.json`. For each
endpoint document, invoke the validator with the kind-specific URL:

- API endpoint → `https://schemas.analitiq.work/api-endpoint/latest.json`.
- Database endpoint (when applicable in future) →
  `https://schemas.analitiq.work/database-endpoint/latest.json`.

Loop fixes until `passed: true` (max 5 iterations per artifact). If
validator still returns `error`-severity findings after 5 passes, halt
and surface the diagnostics to the user.

### 6. Drift

If `previous_release_path` was supplied, invoke
`connector-drift-classifier`. Apply the returned bump to the top-level
`version` of the assembled document.

If `previous_release_path` was not supplied, this is a first release; set
`version` to `1.0.0`.

### 7. Write

Write the connector document and any endpoint files to disk at
predictable paths:

```
{slug}/
├── definition/
│   ├── connector.json
│   └── endpoints/
│       └── {alias}.json   # api connectors only
└── README.md
```

## Failure modes

- Research timeout: ask user for offline-supplied facts or a different docs URL.
- Classification ambiguity: fail closed; ask the user to confirm.
- Validator stuck: surface findings; do not write incomplete files.
- Drift classifier rolls back to `none`: treat as first release.
