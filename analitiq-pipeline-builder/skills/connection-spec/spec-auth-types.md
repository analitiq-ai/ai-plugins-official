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

`none` produces a connection whose `values` envelope contains only
non-secret entries (no secret placeholders, no `.secrets/` files) —
typical for fully public APIs.

## How the agent uses this

1. Read the downloaded connector document. Look at `auth.type`.
2. Load the matching `examples/*.example.json`.
3. Adapt: generate a fresh `connection_id` UUID, set `connector_id` to
   the connector's slug, replace example `values` entries with the
   user's input. For each input whose connector contract bucket is
   `secrets`, write a `"<see .secrets/credentials.json>"` placeholder
   into `values` and add the key to the `.secrets/credentials.json`
   template.
4. Write the `.secrets/<file>.json` template the user fills in.
5. Validate against `connection/latest.json` and pass.

Any `auth.type` not in the table above is a contract violation — halt
and surface a structured refusal note.
