# API auth flows

Per-auth-type authoring contract. Each section lists the required and
forbidden child fields, points at a worked example under `examples/`,
and notes common pitfalls.

## `api_key`

**Required children:** `type`.
**Forbidden:** `authorize`, `token_exchange`, `refresh` (these are OAuth-only).
**`test` is optional.**

The actual API key value is declared in `connection_contract.inputs` with
`secret: true`. Auth header construction happens in the transport's
`headers` block, e.g. `"Authorization": { "template": "Bearer ${secrets.api_key}" }`.

Example: `examples/api-key.example.json`. Variant with templated host:
`examples/api-key-dynamic-host.example.json`.

## `basic_auth`

**Required children:** `type`.
**Forbidden:** OAuth ops.

`username` and `password` are declared as
`connection_contract.inputs`. The `Authorization` header in the transport
should use the `basic_auth` function expression — never pre-compute base64.

```json
"Authorization": {
  "function": "basic_auth",
  "input": {
    "username": { "ref": "connection.parameters.username" },
    "password": { "ref": "secrets.password" }
  }
}
```

Example: `examples/basic-auth.example.json`.

## `oauth2_authorization_code`

**Required children:** `type`, `authorize`, `token_exchange`.
**Optional:** `refresh`, `test`.

`authorize` describes the URL that will be opened in the user's browser
(method usually `GET`); `token_exchange` describes the back-channel
request that swaps the auth code for tokens. Both are
`AuthOperationTemplate` objects with `path` plus optional `method`,
`headers`, `body`, `transport_ref`.

`client_id` typically lives in `connection.parameters` with
`source: "platform"`; `client_secret` lives in `secrets` with
`source: "platform"` and `secret: true`.

Example: `examples/oauth2-authorization-code.example.json` (multi-origin
provider with post-auth discovery).

## `oauth2_client_credentials`

**Required children:** `type`, `token_exchange`.
**Forbidden:** `authorize` (no redirect flow).
**Optional:** `refresh`, `test`.

Used for machine-to-machine auth. The `token_exchange` request POSTs
client credentials and gets an access token.

Example: `examples/oauth2-client-credentials.example.json`.

## `jwt`

**Required children:** `type`.
**Optional:** `test`.

The signing key, algorithm, and claim inputs are declared in
`connection_contract.inputs`. The `Authorization` header uses the
`jwt_sign` function expression:

```json
"Authorization": {
  "template": "Bearer ${auth.access_token}"
}
```

…where `auth.access_token` is produced by an inline `jwt_sign` call in
auth setup. (The exact wiring depends on the provider.)

Example: `examples/jwt.example.json`.

## `credentials`

**Required children:** `type`.
**Optional:** `test`.

Use only when the provider's auth doesn't fit any narrower type. Declare
the credential bundle in `connection_contract.inputs` with appropriate
`secret: true` flags.

## `aws_iam`

**Required children:** `type`.
**Optional:** `test`.
**Forbidden:** OAuth ops.

User-supplied AWS account, role, profile, or credential values are
declared in `connection_contract.inputs`. The transport handles signing
via runtime mechanics — connector JSON declares intent only.

## `none`

**Required children:** `type`.
**Forbidden:** `authorize`, `token_exchange`, `refresh`.

For public APIs that require no authentication. Rare.
