# `selections` and `discovered`

Post-auth outputs are user-picked or auto-discovered values that become
available **after** authentication completes. The connector declares
them in `connection_contract.post_auth_outputs.<name>`.

## `mode: user_selection`

The connector calls a list endpoint after auth, presents the user with
options, the user picks one. The picked value lands in
`connection.selections.<name>`.

```jsonc
// connection
{
  "selections": {
    "profile_id": 123456,
    "tenant_id": "tenant_abc"
  }
}
```

At plugin authoring time, the value is usually **unknown** — the user
hasn't authenticated yet. The plugin can:

- Leave `selections` empty (omit the field). The registry / runtime
  fills it after the user completes the OAuth dance.
- Pre-fill if the user supplies the value upfront ("I already know my
  Wise profile is 123456"). Then write it directly.

## `mode: auto_discovery`

The connector calls a discovery endpoint after auth and stores the
returned value automatically. The destination is one of:

- `connection.discovered.<name>` — visible to runtime templates.
- `secrets.<name>` — stored opaquely (rare; used for derived secrets).

Authored connections **never** populate `discovered` directly. It's
filled at runtime by the platform.

## Common examples

| Connector | Output name | Mode | Stored at |
|---|---|---|---|
| Wise | `profile_id` | user_selection | `selections.profile_id` |
| Pipedrive | `api_domain` | auto_discovery | `discovered.api_domain` |
| Xero | `tenant_id` | user_selection | `selections.tenant_id` |
| AWS IAM | `account_id` | auto_discovery | `discovered.account_id` |

## Plugin behavior

The plugin **may** ask the user upfront for `user_selection` values
when their identity is obvious from context ("you're connecting to
Wise — what's the profile ID?"). Otherwise, the plugin authors the
connection with these blocks empty/omitted and the registry/runtime
fills them when the user completes the auth flow.
