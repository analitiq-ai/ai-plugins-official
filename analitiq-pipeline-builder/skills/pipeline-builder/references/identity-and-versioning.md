# Identity and versioning

Pipelines, streams, and connections reference each other by **alias**.
Aliases are short stable slugs (`^[a-z0-9][a-z0-9_-]*$`) the user
provides up front; the plugin authors them directly into the relevant
fields. The engine resolves aliases to internal identifiers at runtime.

## Where aliases appear in authored documents

| Field | Holds |
|---|---|
| `pipeline.alias` | the pipeline alias |
| `pipeline.connections.source` | the source side's connection alias |
| `pipeline.connections.destinations[]` | each destination connection alias |
| `pipeline.streams[]` | each stream's alias |
| `stream.alias` | the stream alias |
| `stream.pipeline_id` | the parent pipeline's alias |
| `stream.source.endpoint_ref.connection_id` | the source connection alias (matches `pipeline.connections.source`) |
| `stream.destinations[].endpoint_ref.connection_id` | each destination connection alias (one of `pipeline.connections.destinations[]`) |
| `connection.alias` | the connection alias |
| `connection.connector_alias` | the connector slug the connection instantiates |
| `database_endpoint.alias` | the endpoint alias |

The published schemas accept any non-empty string for these reference
fields. Patterns are not enforced — interpretation is the engine's job.

## Server-managed `version` field

Pipelines and streams have a server-managed integer `version` field.
**The plugin does not author it.** The registry sets `version: 1` on
insert and increments on certain updates per the published lifecycle
contract.

This is different from connectors, which use semver and a drift
classifier to bump the field. Pipelines and streams use a counter, and
the registry owns it.