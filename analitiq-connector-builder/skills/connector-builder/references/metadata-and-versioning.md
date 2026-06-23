# Metadata and versioning

Excerpts from `docs/schema-contracts/shared/identity-and-versioning.md`
and `connectors/connector-schema-parameterization.md`.

## Authored top-level fields

| Field | Required | Notes |
|---|---|---|
| `$schema` | Yes (for standalone files) | Fixed const: `https://schemas.analitiq.ai/connector/latest.json`. The validator fetches from the same host. |
| `kind` | Yes | One of `api`, `database`, `file`, `s3`, `stdout`. |
| `connector_id` | Yes (plugin-authored) | Stable connector slug, lowercase `[a-z0-9_-]+`. Same value as the on-disk `{connector_id}/` directory name. Per the contract `connector_id` is *optional* on submission — the registry assigns one when omitted — but this plugin always emits it so the directory name and identifier stay in sync. |
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

Note: the connector's type maps are **not** top-level fields. They ship
as separate sibling artifacts — `{connector_id}/definition/type-map-read.json`
(native → Arrow, all kinds) and `{connector_id}/definition/type-map-write.json`
(Arrow → native, database only) — validating against
`https://schemas.analitiq.ai/type-map-read/latest.json` and
`https://schemas.analitiq.ai/type-map-write/latest.json` respectively. See
`connector-spec-db/spec-type-maps.md` for authoring.

## Authoring `connector_id`

The plugin authors `connector_id` on every connector document. The same
value names the on-disk directory (`{connector_id}/`), so the contract
path `connectors/{connector_id}/definition/connector.json` and the
plugin's output path align without a rewrite layer.

The schema permits `connector_id` to be any non-empty string (UUID or
slug); this plugin uses the slug convention `[a-z0-9_-]+` to keep
directory names portable.

## Registry-stamped fields

The following fields are stamped by the registry on insert/update and
must not appear in authored documents:

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
| Patch | No connection drift. | Bug fixes, doc fixes, transport implementation tuning, type-map rule reordered (when the reorder does not change first-match resolution for any existing input). |
| Minor | Additive, non-drifting. | Optional input added, optional discovery output added, optional endpoint added, type-map rule added. |
| Major | Possible connection drift. | Input removed, renamed, type-changed, enum narrowed, storage moved, non-optional input added, auth-shape change, discovery-shape change, type-map rule removed, render side changed for an existing matcher (read map: `canonical` changed for an existing `native`; write map: `native` changed for an existing `canonical`). |

Type-map drift categories apply per file: `type-map-read.json` and
`type-map-write.json` are diffed independently, and a change in either
drives the bump per the table above.

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
different URL — the JSON Schema validator will reject it. The validator
fetches from the same host.
