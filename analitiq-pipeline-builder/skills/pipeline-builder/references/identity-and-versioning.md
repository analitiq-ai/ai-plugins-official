# Identity and versioning

Pipelines, streams, and connections each carry an RFC-4122 UUID
**identity field** (`pipeline_id`, `stream_id`, `connection_id`) that the
plugin authors directly. Connectors and database endpoints use **slug
identifiers** (`connector_id`, `endpoint_id`) the user / plugin chooses.
Directory names on disk stay human-readable slugs and are independent
of the UUID identity stored inside the documents.

## Identity fields per entity

| Field | Form | Authored by | Notes |
|---|---|---|---|
| `pipeline.pipeline_id` | RFC-4122 UUID | plugin (or service-assigned if omitted) | Schema regex enforces UUID format. |
| `stream.stream_id` | RFC-4122 UUID | plugin (or service-assigned if omitted) | Schema regex enforces UUID format. |
| `stream.pipeline_id` | string cross-reference | plugin | Must equal parent pipeline's `pipeline_id` UUID. |
| `connection.connection_id` | RFC-4122 UUID | plugin (or service-assigned if omitted) | Schema regex enforces UUID format. |
| `connection.connector_id` | non-empty string (UUID **or** slug) | plugin | Required. The connector slug (e.g. `"wise"`, `"postgresql"`) is the common form. |
| `database_endpoint.endpoint_id` | slug, `^[a-z0-9][a-z0-9_-]*$` | plugin | Required. Unique within the owning connection. |

The plugin generates UUIDs locally for `pipeline_id`, `stream_id`, and
`connection_id`. The orchestrator keeps the generated UUIDs in memory so
sibling documents written in the same run can cross-reference them
correctly.

## Cross-document references

These fields are non-empty strings whose **value** must match the
corresponding identity field of the referenced document. The schema does
not constrain the form of references; engines resolve at runtime.

| Reference field | Must equal |
|---|---|
| `pipeline.connections.source` | the source `connection.connection_id` UUID |
| `pipeline.connections.destinations[]` | each destination `connection.connection_id` UUID |
| `pipeline.streams[]` | each child `stream.stream_id` UUID |
| `stream.pipeline_id` | the parent `pipeline.pipeline_id` UUID |
| `stream.source.endpoint_ref.connection_id` | the source `connection.connection_id` UUID |
| `stream.destinations[].endpoint_ref.connection_id` | each destination `connection.connection_id` UUID |
| `stream.source.endpoint_ref.endpoint_id` | the source `endpoint_id` slug (DB endpoint) or connector endpoint key (API) |
| `stream.destinations[].endpoint_ref.endpoint_id` | the destination endpoint slug / key |

## Directory layout vs. document identity

Directories use human-readable slugs:

```
pipelines/<pipeline-slug>/pipeline.json
pipelines/<pipeline-slug>/streams/<stream-slug>.json
connections/<connection-slug>/connection.json
connections/<connection-slug>/endpoints/<endpoint-slug>.json
```

The slug is **only** used for file organization. Cross-document refs
inside the JSON use the UUID identities, not the slugs. The
`pipeline-stream-consistency` validator finds stream files by walking
`pipelines/<slug>/streams/` and then compares the UUIDs inside the
documents.

## Server-managed `version` field

Pipelines and streams have a server-managed integer `version` field.
**The plugin does not author it.** The registry sets `version: 1` on
insert and increments on certain updates per the published lifecycle
contract.

This is different from connectors, which use semver and a drift
classifier to bump the field. Pipelines and streams use a counter, and
the registry owns it.
