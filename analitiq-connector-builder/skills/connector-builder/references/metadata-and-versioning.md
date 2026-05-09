# Metadata and versioning

Excerpts from `docs/schema-contracts/shared/identity-and-versioning.md`
and `connectors/connector-schema-parameterization.md`.

## Authored top-level fields

| Field | Required | Notes |
|---|---|---|
| `$schema` | Yes (for standalone files) | Fixed const: `https://schemas.analitiq.ai/connector/latest.json`. The schema host inside the doc is `.ai` (production); the *fetch* host the validator uses is `.work` (current dev). |
| `kind` | Yes | One of `api`, `database`, `file`, `s3`, `stdout`. |
| `alias` | Yes | Stable connector slug. Lowercase, `[a-z0-9_-]`. Immutable in the registry. |
| `display_name` | No | User-facing label. |
| `description` | No | Human-readable summary. |
| `tags` | No | Search/grouping labels. |
| `documentation_url` | No | Provider docs URL. |
| `version` | Yes | Semantic version string. Start at `1.0.0` for first release. |
| `default_transport` | Yes | Name of an entry in `transports`. |
| `transports` | Yes | Map of named transport contracts. |
| `transport_defaults` | No | Defaults merged into named transports. |
| `auth` | Yes | Auth workflow definition. |
| `connection_contract` | Yes | Connection-contract shape. |
| `resource_discovery` | No | Resource discovery declarations. |
| `type_maps` | No (db: should declare) | Connector-packaged type maps. |
| `x-*` | No | Extension metadata. |

## Server-managed fields (NEVER author)

These four fields are stamped by the registry on insert/update and must
not appear in authored documents:

- `connector_id`
- `connector_schema_version`
- `created_at`
- `updated_at`

The published schema reflects this — the authoring shape does not list
them in `properties` or `required`. The plugin's `reserved-field`
validator flags them as errors if they appear.

## Release version (`version`)

Authored top-level `version` is a semver string. It bumps according to
the connector release table:

| Bump | Meaning | Examples |
|---|---|---|
| Patch | No connection drift. | Bug fixes, doc fixes, transport implementation tuning. |
| Minor | Additive, non-drifting. | Optional input added, optional discovery output added, optional endpoint added, type-map entries added. |
| Major | Possible connection drift. | Input removed, renamed, type-changed, enum narrowed, storage moved, non-optional input added, auth-shape change, discovery-shape change. |

The drift-classifier sub-agent computes this bump from a diff between
the previous release and the new draft.

## First release

If no `previous_release_path` is supplied, set `version: "1.0.0"`.

## Schema URL declaration

Authored connector files declare:

```json
{ "$schema": "https://schemas.analitiq.ai/connector/latest.json" }
```

This is locked by a `const` inside the published schema. Do not write a
different URL — the JSON Schema validator will reject it. Note this is
the production host; the validator currently fetches from `.work`
(dev), but the in-document declaration uses `.ai`.
