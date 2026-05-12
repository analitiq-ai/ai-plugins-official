# Auth type → template mapping

The connector's `auth.type` selects which `examples/*.example.json` to
load. The orchestrator's `AuthTypeMapper`
(`../pipeline-builder/references/enum-mappers.md`) drives this.

| `auth.type` | template | `.secrets/` files |
|---|---|---|
| `api_key` | `examples/api-key.example.json` | `credentials.json` |
| `basic_auth` | `examples/basic-auth.example.json` | `credentials.json` |
| `oauth2_authorization_code` | `examples/oauth2-authorization-code.example.json` | `credentials.json` + `client.json` |
| `oauth2_client_credentials` | `examples/oauth2-client-credentials.example.json` | `credentials.json` + `client.json` |
| `jwt` | `examples/jwt.example.json` | `credentials.json` (with `private_key`) |
| `db` | `examples/db.example.json` | `credentials.json` (with `password`) |
| `credentials` | `examples/credentials.example.json` | `credentials.json` |
| `aws_iam` | `examples/aws-iam.example.json` | `credentials.json` (with `aws_access_key_id`, `aws_secret_access_key`) |
| `none` | `examples/none.example.json` | (none) |

`none` produces a connection with no `secret_refs` and no `.secrets/`
files — typical for fully public APIs that need only an alias and
optional parameters.

## How the agent uses this

1. Read the downloaded connector document. Look at `auth.type`.
2. Load the matching `examples/*.example.json`.
3. Adapt: replace example aliases with the user's alias, replace example
   parameter values with the user's input, replace example `secret_refs`
   paths with the plugin convention `secrets/<alias>/<key>`.
4. Write the `.secrets/<file>.json` template the user fills in.
5. Validate against `connection/latest.json` and pass.

Any `auth.type` not in the table above is a contract violation — halt
and surface a structured refusal note.
