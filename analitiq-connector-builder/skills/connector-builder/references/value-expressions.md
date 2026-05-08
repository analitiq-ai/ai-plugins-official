# Value expressions

Shared invariant both creator agents must follow. Excerpted from the
authoritative spec at
`docs/schema-contracts/shared/value-expression-parameterization.md`.

## Four expression kinds

A value expression is one of:

| Kind | Shape | Use |
|---|---|---|
| `ref` | `{"ref": "<dotted.path>"}` | Resolve a single value from a runtime scope. |
| `template` | `{"template": "literal-with-${scope.path}-interpolation"}` | Build a string by interpolating one or more refs into a literal. |
| `literal` | `{"literal": <any>}` | A constant value (string, number, boolean, object, array). |
| `function` | `{"function": "<name>", "input": {...}}` | Call a registered function with named inputs. |

Anywhere the schema accepts a value expression, exactly one of the four
shapes is allowed.

## Logical scopes (closed list)

Every `ref` and every `${...}` interpolation inside a `template` must
target one of these scopes:

| Scope | Phase available | Holds |
|---|---|---|
| `secrets.*` | `auth` and later | User-entered or platform-injected secret values, opaque references. |
| `connection.parameters.*` | `pre_auth` and later | Non-secret user/platform values declared in `connection_contract.inputs` with `storage: "connection.parameters"`. |
| `connection.selections.*` | `post_auth` and later | Durable user choices declared as `post_auth_outputs` with `storage: "connection.selections"`. |
| `connection.discovered.*` | `post_auth` and later | Auto-discovered non-secret context (e.g. `api_domain`) declared as `post_auth_outputs` with `storage: "connection.discovered"`. |
| `auth.*` | `auth` and later | Auth tokens (access_token, refresh_token, expiry). |
| `runtime.*` | varies by ref | OAuth state, redirect URI, PKCE verifier, code (transient values per `lifecycle-phases.md`). |
| `stream.*` | per stream | Stream-owned routing, tenant context, stream-specific auth context. |

Any other scope is an `expression-resolver` validation error.

## Function catalog (registered)

Inline function expressions may only call registered functions. Current
catalog:

- `basic_auth` — produce `Basic <base64(username:password)>` from `username` and `password` inputs.
- `jwt_sign` — sign a JWT from `key`, `algorithm`, and `claims` inputs.
- `url_encode` — percent-encode a string for use as a URL component.

Unknown functions are validation errors. To extend the catalog, the
engine's function registry must be updated first; do not invent function
names in connector JSON.

## DSN placeholders are not value expressions

Inside `dsn.template`, `{placeholder}` markers are NOT `${...}` value
expressions. They resolve through `dsn.bindings`, where each binding
declares a `value` (a value expression) and an `encoding` (closed enum).

This is intentional: the runtime owns percent-encoding mechanics for DSN
construction and applies declared encodings before substitution.
Connector authors must not pre-encode binding values.
