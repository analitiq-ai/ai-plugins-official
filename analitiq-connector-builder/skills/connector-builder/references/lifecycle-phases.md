# Lifecycle phases

Excerpted from `docs/schema-contracts/shared/lifecycle-phases.md`. Used
by `phase-resolvability` validation and by the creator agents when they
declare which phase produces each value.

## Phases

| Phase | Available scopes | Used by |
|---|---|---|
| `pre_auth` | `connection.parameters.*` | Inputs the user submits before auth (host, port, region, tenant slug, …). Transports for pre-auth discovery may run here. |
| `auth` | `pre_auth` scopes + `secrets.*`, `runtime.oauth.*` | Auth operations (`authorize`, `token_exchange`, `refresh`). |
| `post_auth` | `auth` scopes + `auth.*` | Post-auth discovery requests, `options_request`, `discovery_request`. |
| `active` | `post_auth` scopes + `connection.selections.*`, `connection.discovered.*`, `stream.*` | Endpoint operations. |

A later phase may use any earlier phase's scopes.

## Resolvability rule

For every transport's references, compute the union of scopes used. The
transport must be invokable in a phase where every used scope is
available. If a transport references `connection.discovered.api_domain`,
it cannot be the `default_transport` for an operation that runs in
`auth` or earlier.

## Example: Pipedrive

Pipedrive's `default_transport` (`api`) uses
`connection.discovered.api_domain`, which is populated only after
post-auth discovery. So Pipedrive declares a separate `discovery`
transport for the post-auth `discovery_request` that produces
`api_domain`. Once discovery completes, normal API calls can use the
`api` transport.

## Validator findings

`phase-resolvability` flags the common error of a transport using
`connection.discovered.*` without a documented post-auth output that
produces it. Other phase mismatches require declaring `phase` on each
input correctly.

## Runtime OAuth scope

`runtime.oauth.state`, `runtime.oauth.redirect_uri`, and
`runtime.oauth.pkce_verifier` are available in both `auth.authorize` and
`auth.token_exchange`. `runtime.oauth.code` is available only in
`auth.token_exchange`. These values are never persisted.
