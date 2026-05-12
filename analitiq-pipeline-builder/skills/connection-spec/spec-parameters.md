# `parameters` and `discovered` routing

A connection stores user-submitted **values**. The connector document
declares **where each value goes** via
`connection_contract.inputs.<name>.storage`. Author the connection by
mirroring that routing.

## `connection_contract.inputs.<name>.storage` → where in the connection

| `storage` value | connection field | example |
|---|---|---|
| `connection.parameters` | `parameters.<name>` | `parameters.host = "db.example.com"` |
| `secrets` | `secret_refs.<name>` | `secret_refs.password = "secrets/production_postgresql/password"` |

For `connection_contract.post_auth_outputs.<name>.storage`:

| `storage` value | connection field |
|---|---|
| `connection.selections` | `selections.<name>` |
| `connection.discovered` | `discovered.<name>` |
| `secrets` | `secret_refs.<name>` |

## Type coercion

The connector declares the JSON type of each input
(`type: string|integer|number|boolean|array|object`). The connection's
`parameters` block must use the matching JSON type — not a stringified
form. For example, a port number is `5432` (integer), not `"5432"`
(string).

The plugin does not coerce types automatically. Ask the user for the
right type or read it from the connector.

## Optional inputs

Inputs declared with `required: false` may be omitted from
`parameters`. The connector's `default` value (if declared) applies at
runtime — the plugin should **not** copy the default into the
connection unless the user explicitly wants to override it (which is
a no-op when the value equals the default).

## Enum-constrained inputs

Inputs with `enum: […]` constrain the connection's value to one of the
listed strings. Common example: `ssl_mode` ∈
`{none, require, verify-ca, verify-full, prefer}` (or the connector's
own variant). The plugin echoes whatever the user picks; the registry
validates the enum at save time.
