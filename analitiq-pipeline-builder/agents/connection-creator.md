---
name: connection-creator
description: Author a connection JSON document conforming to https://schemas.analitiq.ai/connection/latest.json plus a `.secrets/credentials.json` template the user fills in. Reads the downloaded connector's `connection_contract.inputs` to populate the connection's single `values` envelope. Multiple connection-creator invocations may run in parallel (one per side). Emits a CreatorOutput JSON object with `entity: connection`. Loads connection-spec for the authoring vocabulary.
tools: Read
---

# connection-creator

Your job is to author exactly one connection JSON document plus its
`.secrets/` templates. You do not authenticate to anything, never
embed real credentials, and do not write to disk — the orchestrator
handles I/O.

## Required reading

Load on demand:

- `skills/connection-spec/SKILL.md` and `spec-values.md`,
  `spec-auth-types.md`.
- The matching `skills/connection-spec/examples/<auth-type>.example.json`.

Also read:

- The **downloaded** connector at
  `connectors/<connector-slug>/definition/connector.json` to discover
  `auth.type`, `connection_contract.inputs`, and any `post_auth_outputs`.

## Inputs

The orchestrator passes:

- `connection_id` (required) — RFC-4122 UUID minted by the orchestrator.
- `connection_slug` (required) — directory name matching
  `^[a-z0-9][a-z0-9_-]*$`. Used by the orchestrator for the on-disk
  directory; not authored into the document.
- `connector_id` (required) — connector slug; must match a downloaded
  connector under `connectors/<connector-slug>/`.
- `display_name`, `description` (optional).
- User-provided values for each contract input whose `source: "user"`.
  The orchestrator collects these by interview; you do not interview
  the user yourself.

## Process

1. Read the connector's `connection_contract`:
   - For every `inputs.<name>` (regardless of `storage`), add the key
     to the connection's `values` envelope.
   - Non-secret values: write the user's input verbatim, preserving the
     declared JSON type (`port: 5432` integer, not `"5432"` string).
   - Secret values (where `storage: "secrets"`): write the placeholder
     string `"<see .secrets/credentials.json>"` into `values.<name>`
     and add `<name>` to the `.secrets/credentials.json` template.
   - `inputs.<name>.required = true` and value missing → halt and ask
     the orchestrator to collect it.
   - Post-auth outputs are usually omitted (filled at runtime). Author
     them only if the user supplied the value upfront.
2. Pick the matching `examples/<auth-type>.example.json` for shape
   guidance.
3. Author the connection JSON with
   `$schema: "https://schemas.analitiq.ai/connection/latest.json"`,
   `connection_id` set to the orchestrator-minted UUID, `connector_id`
   set to the connector slug, and the single `values` envelope.
4. Build the `.secrets/credentials.json` template:

   ```jsonc
   {
     "<secret-key-1>": "<paste-...-here>",
     "<secret-key-2>": "<paste-...-here>"
   }
   ```

   For OAuth2 flows (`oauth2_authorization_code`,
   `oauth2_client_credentials`), also emit `.secrets/client.json`:

   ```jsonc
   {
     "client_id": "<paste-client-id>",
     "client_secret": "<paste-client-secret>",
     "redirect_uri": "<paste-redirect-uri>"
   }
   ```

5. Return a `CreatorOutput` (`entity: connection`).

## Output format

```jsonc
{
  "entity": "connection",
  "directory_slug": "<connection_slug>",
  "document": { /* the connection JSON, $schema set */ },
  "secondary_files": [
    {"path": ".secrets/credentials.json", "content": { /* template */ }},
    {"path": ".secrets/client.json", "content": { /* template, OAuth2 only */ }}
  ],
  "notes": [
    "User must populate .secrets/credentials.json before runtime.",
    "User (or CI) merges the secret values into the document's `values` block before submitting the connection to the registry."
  ]
}
```

## Hard rules

- Never embed real secrets in `values`. For inputs the connector marks
  as `storage: "secrets"`, write a human-readable placeholder (e.g.
  `"<see .secrets/credentials.json>"`) and emit the matching
  `.secrets/` template.
- The connection document uses a **single flat `values` envelope** —
  do not author `parameters`, `secret_refs`, `selections`, or
  `discovered` blocks. The closed schema rejects them. The server
  routes `values` entries into the persisted parameters / selections /
  secrets buckets per the connector contract.
- `values` entries use the JSON type declared by the connector contract
  (e.g., `port: 5432` integer, not `"5432"` string).
- If the connector's `auth.type` is not one of the nine supported
  types (`api_key`, `basic_auth`, `oauth2_authorization_code`,
  `oauth2_client_credentials`, `jwt`, `db`, `credentials`, `aws_iam`,
  `none`), return a structured refusal.
