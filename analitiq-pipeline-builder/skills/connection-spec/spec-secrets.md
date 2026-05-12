# `secret_refs` format

A `secret_refs` value is **always a reference string**, never the
secret itself. The published schema enforces one of these prefixes:

| Prefix pattern | Where the secret lives |
|---|---|
| `secrets/<path>` | Generic secret-store path (most common for plugin output). |
| `connections/<path>` | Catalog-managed connection-scoped secrets. |
| `ssm:/<path>` | AWS Systems Manager Parameter Store. |
| `arn:aws:secretsmanager:<region>:<acct>:secret:<id>` | AWS Secrets Manager. |
| `arn:aws:ssm:<region>:<acct>:parameter/<id>` | SSM Parameter Store full ARN. |
| `s3://<bucket>/<key>` | S3 object (used for cert bundles, JWT keys). |

The `secret-ref-format` Layer 2 validator rejects anything else.

## Plugin convention

When the plugin writes a new connection, it emits each reference as:

```
secrets/<connection-alias>/<input-name>
```

For example, for `alias: production_postgresql` and the inputs
`password` + `ssl_ca_certificate`:

```jsonc
{
  "secret_refs": {
    "password": "secrets/production_postgresql/password",
    "ssl_ca_certificate": "secrets/production_postgresql/ssl_ca_certificate"
  }
}
```

The plugin also writes a `.secrets/credentials.json` template:

```jsonc
{
  "password": "<paste-password-here>",
  "ssl_ca_certificate": "<paste-PEM-bundle-here>"
}
```

The user fills in the template. The registry never reads from
`.secrets/` directly; the user is expected to upload the secrets to
their secret store (AWS Secrets Manager, SSM, etc.) and then rewrite
the `secret_refs.<key>` to the corresponding ARN or path *before
submission*.

## OAuth2 special case

OAuth2 connector flows additionally need a client app's
`client_id` and `client_secret`. The plugin emits a separate
`.secrets/client.json` template:

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
