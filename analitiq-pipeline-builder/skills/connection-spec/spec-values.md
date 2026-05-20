# The `values` envelope

A connection authors a **single flat `values` envelope** keyed by
connection-contract input name and post-auth-output name. The server
routes each entry into the persisted parameters / selections / secrets
bucket per the connector's `connection_contract` — the plugin does not
split keys into separate buckets.

```jsonc
{
  "values": {
    "host": "db.example.com",
    "port": 5432,
    "ssl_mode": "verify-full",
    "password": "<see .secrets/credentials.json>"
  }
}
```

## Where keys come from

Read the connector document. Each entry under
`connection_contract.inputs.<name>` and
`connection_contract.post_auth_outputs.<name>` becomes a `values.<name>`
key. The connector's `storage` field decides server-side routing — the
plugin does not need to mirror it in the authored document.

| Connector contract field | Authored as |
|---|---|
| `connection_contract.inputs.<name>` (any `storage`) | `values.<name>` |
| `connection_contract.post_auth_outputs.<name>` (any `storage`) | `values.<name>` (only when the value is known upfront) |

Post-auth outputs (`user_selection` / `auto_discovery`) are usually
**unknown at plugin authoring time** — the user hasn't authenticated yet.
Omit them; the runtime fills them after the user completes the auth flow.

## Type coercion

The connector declares the JSON type of each input
(`type: string|integer|number|boolean|array|object`). The
connection's `values` entry must use the matching JSON type — not a
stringified form. For example, a port number is `5432` (integer), not
`"5432"` (string). The plugin does not coerce types automatically; ask
the user or read the type from the connector.

## Optional inputs

Inputs declared with `required: false` may be omitted from `values`. The
connector's `default` value (if declared) applies at runtime — the plugin
should **not** copy the default into the connection unless the user
explicitly wants to override it.

## Enum-constrained inputs

Inputs with `enum: […]` constrain the connection's value to one of the
listed strings. Common example: `ssl_mode` ∈
`{none, require, verify-ca, verify-full, prefer}` (or the connector's
own variant). The plugin echoes whatever the user picks; the registry
validates the enum at save time.

## Secrets workflow

For inputs whose connector contract sets `storage: "secrets"`, do
**not** write the secret value into `values`. Instead:

1. Author `values.<name>` with a human-readable placeholder string, e.g.
   `"<see .secrets/credentials.json>"`. The placeholder is local — it
   signals to the user (and to submission tooling) that the real value
   lives outside the authored document.
2. Emit a sibling `.secrets/credentials.json` template the user fills in:

   ```jsonc
   {
     "password": "<paste-password-here>",
     "ssl_ca_certificate": "<paste-PEM-bundle-here>"
   }
   ```

3. The user (or CI) merges secret values from `.secrets/credentials.json`
   into the `values` block before submitting the connection to the
   registry. The registry never reads `.secrets/` directly.

### OAuth2 special case

OAuth2 connector flows additionally need a client app's `client_id` and
`client_secret`. The plugin emits a separate `.secrets/client.json`
template:

```jsonc
{
  "client_id": "<paste-client-id>",
  "client_secret": "<paste-client-secret>",
  "redirect_uri": "<paste-redirect-uri>"
}
```

These map to the connector's pre-auth secret inputs. The
`connection-creator` agent picks the matching example based on
`connector.auth.type` (see `spec-auth-types.md`).
