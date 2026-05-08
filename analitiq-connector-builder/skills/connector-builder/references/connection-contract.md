# Connection contract — outer shape

Both creator agents (api and db) must emit the same outer
`connection_contract` shape. Concrete inputs differ; the structure does
not.

## Top-level fields

| Field | Required | Notes |
|---|---|---|
| `inputs` | Yes | Map of input keys to `ConnectionContractInput` declarations. May be empty. |
| `post_auth_outputs` | No | Map of durable post-auth output keys to `PostAuthOutput` declarations. |
| `required_for_activation` | No | Array of reference paths that must resolve before the connection can become active (e.g. `"connection.discovered.api_domain"`). |
| `validation` | No | Cross-input validation rules. |

## Per-input fields (`ConnectionContractInput`)

Required: `source`, `phase`, `storage`, `type`, `required`.

| Field | Values |
|---|---|
| `source` | `"user"` (entered by end user) or `"platform"` (provisioned by the platform/admin). |
| `phase` | `"pre_auth"` or `"auth"` — when the value must be available. |
| `storage` | `"connection.parameters"` (non-secret, durable), `"secrets"` (secret, durable, materialized via secret refs), `"connection.selections"` or `"connection.discovered"` (filled later by post-auth outputs, not at input-collection time). |
| `type` | JSON Schema type: `string`, `integer`, `boolean`, `number`. |
| `required` | Boolean. |
| `secret` | Boolean (default false). Must be true for any input stored in `secrets`. |
| `enum` | Array of allowed values (closed enum). |
| `default` | Default value (for non-required inputs). |
| `format` / `pattern` | Optional validation — e.g. `format: "uri"` or a regex `pattern`. |
| `ui` | Optional UI hint object (label, placeholder, widget). |

## API vs DB inputs

Both kinds emit the same outer shape. Concrete inputs differ:

- **API connectors** — typically declare `api_key`, OAuth `client_id`/`client_secret`, optional region/subdomain/tenant fields used to template `base_url`.
- **DB connectors** — typically declare `host`, `port`, `database`, `username`, `password`, `ssl_mode`, `ssl_ca_certificate`.

## Post-auth outputs

`post_auth_outputs` are the single source of truth for durable post-auth
context. Required fields per output:

- `mode` — discovery mode (e.g. `discovered`, `selected`).
- `storage` — `"connection.selections"` for user choices, `"connection.discovered"` for auto-discovered values.
- `type` — the value's type.
- `value_path` — the reference path the runtime materializes (e.g. `"connection.discovered.api_domain"`).

Discovery mechanics (`options_request` / `discovery_request`) are
declared in the same output entry where applicable.

## Drift detection

The `connection_contract` block has no standalone `version`. Drift
detection rides on the connector's top-level `version` semver:

- Additive changes to inputs/outputs/activation/validation → minor bump.
- Breaking changes (input removed, renamed, type-changed, enum narrowed,
  storage moved, non-optional input added) → major bump.

See `metadata-and-versioning.md` and the connector release table.
