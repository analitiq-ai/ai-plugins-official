---
name: connector-wizard
color: green
description: >
  This skill should be used when the user wants to build, create, or scaffold a new connector
  or add endpoints to an existing connector. Common triggers: "build a connector for [system]",
  "create a new API connector", "add a PostgreSQL connector", "create endpoints for Shopify",
  "scaffold a connector for Wise", "add an S3 connector". Handles the full lifecycle: interview,
  duplicate check, research, connector creation, endpoint creation (API only), optional
  validation, and optional community contribution to the registry.
argument-hint: "<system name and optional API docs URL>"
model: inherit
allowed-tools: Read, Glob, Grep, Bash, WebFetch, WebSearch, Agent
---

Interview the user, collect requirements for a connector and its endpoints, then dispatch the
appropriate agents for the build process.

Build **one connector at a time** for a single system.

## What You Need to Determine

1. **System to connect** — what system the connector is for:
   - Which specific system? (e.g., Wise, Xero, PostgreSQL, MySQL, Shopify, S3, SFTP)
   - What type? API, database, or other (file/storage)?
   - If API: does the user have a link to the API documentation?

2. **Endpoints to register** — **API connectors only**:
   - Which specific API endpoints? (e.g., `/v1/transfers`, `/v1/accounts`)
   - What fields are important?
   - Are there any filters (e.g., date ranges, status filters)?

   > **Database and other connectors do NOT have pre-defined endpoints.** Their "endpoints" are
   > schema/table combinations (e.g., `public/users`) that are specific to each deployment and
   > discovered at runtime. Do NOT ask about endpoints for database or other connector types.

## Interview Flow

1. Ask what system the user wants to create a connector for.
2. Determine the connector type (API, database, other).
3. **If API**: ask about specific endpoints the user wants to register and whether they have a documentation URL.
4. **If database or other**: skip endpoint questions — these connectors do not have pre-defined endpoints.
5. Check for `ANALITIQ_API_KEY` (see Validation section below) — env var first, then ask user.
6. Summarize the requirements back to the user for confirmation.

## Requirements Output

When requirements are confirmed, produce a structured summary:

```
## Connector Requirements Summary

### Connector
- System: {name}
- Type: {api|database|other}
- Connector slug: {name}
- Documentation URL: {url if provided, API only}

### Endpoints (API connectors only)
- {list of endpoints to register}
```

---

## Duplicate Check — MANDATORY

Before dispatching any agents, you MUST check whether a connector already exists in the public
DIP registry.

Connectors in the registry are named `{slug}`.

### How to check

1. Fetch the registry index (no authentication needed):
   ```
   curl -s https://raw.githubusercontent.com/analitiq-dip-registry/.github/main/registry.json | jq '.connectors[].slug'
   ```

2. **Search for similar names** — the connector may exist under a slightly different slug.
   For example, if the user wants "Pipe Drive", check for `connector-pipedrive`, `connector-pipe-drive`, etc.
   Compare the user's requested name against all repos in the org.

3. If the connector already exists:
   - Tell the user it already exists and provide the repo URL: `https://github.com/analitiq-dip-registry/{name}`
   - Ask if the user can use the existing connector as-is
   - **If yes** — the conversation ends here. No further action needed.
   - **If no** — ask what's wrong. Is the connector outdated? Is some information incorrect?
     Then proceed with research to get updated information and rebuild/update the connector.
   - For API connectors: ask if they want to add new endpoints to the existing connector

4. If the connector does not exist, proceed with creation.

---

## Orchestration — MANDATORY

After the user confirms the requirements summary and the duplicate check passes (or the user
wants to update an existing connector), execute the following phases. Do NOT create connector
or endpoint JSON yourself — use the agents.

### Phase 1 — Research

Research the system to gather the information needed for connector creation.

1. Read the matching research brief from this skill's directory:
   - API: `${CLAUDE_PLUGIN_ROOT}/skills/connector-wizard/research-brief-api.md`
   - Database: `${CLAUDE_PLUGIN_ROOT}/skills/connector-wizard/research-brief-db.md`
   - Storage/other: `${CLAUDE_PLUGIN_ROOT}/skills/connector-wizard/research-brief-storage.md`

2. Fill in the system name and documentation URL in the brief.

3. Dispatch the **`connector-researcher`** agent with the filled research brief.

4. Review the research results for completeness. If critical information is missing, ask the user
   to provide it or dispatch another research query.

5. **Deprecation check**: If the research results indicate the system or API is deprecated
   (`"deprecated": true`):
   - Warn the user that this system/API is deprecated.
   - Ask if they still want to proceed. The user may need a deprecated-but-functional connector.
   - **If yes** — proceed. The connector will be tagged as deprecated in the manifest.
   - **If no** — stop here. Suggest the recommended replacement if one was found.
   - For API connectors with multiple auth methods: individual auth methods may be deprecated
     independently (e.g., API key auth deprecated but OAuth2 still active). Filter out deprecated
     methods before presenting options in Phase 1.5, unless ALL methods are deprecated — then
     warn and ask.

### Phase 1.5 — Multi-Auth Selection (API connectors only)

If the research results contain multiple auth methods in `auth_methods`:

1. **Present the options** to the user. List each auth method with a brief description:
   - e.g., "Shopify supports two authentication methods:
     1. **OAuth2 Authorization Code** — requires a registered app on the Shopify Partner Dashboard
     2. **API Key** — uses a private app API key, simpler setup"
2. **Ask the user which method they want** for this connector.
3. **Update the slug** to include the auth method suffix:
   - If only one auth method exists → `{system}` (no suffix)
   - If multiple exist → `{system}-{auth_method}` (e.g., `shopify-oauth2`,
     `shopify-api-key`)
   - Use short suffixes: `oauth2` (not `oauth2-authorization-code`), `api-key`, `basic-auth`,
     `client-credentials`, `jwt`
4. **Re-run the duplicate check** against the auth-specific slug before proceeding.
5. **Extract the chosen auth method** from `auth_methods` and pass only that method's data
   (along with the shared fields like `base_url`, `requests_per_second`, `timeout`) to Phase 2.

If only one auth method was returned, skip this phase entirely — no suffix needed, proceed directly.

### Phase 1.6 — Category Selection

Fetch `https://raw.githubusercontent.com/analitiq-dip-registry/.github/main/categories.json`,
auto-suggest the best match based on the system and research results (e.g. Shopify →
`e_commerce_platforms`), and confirm with the user. Record the chosen entry's
`connector_group_id` — this is passed to Phase 2 as `category_id` and written to
`connector.json`. If the fetch fails, ask the user whether to proceed without a category
or abort.

### Phase 2 — Build connector

Dispatch the matching type-specific connector creator agent with the research results and
the `category_id` from Phase 1.6 as context:

- **API connectors**: dispatch **`api-connector-creator`** with the chosen auth method's data
- **Database connectors**: dispatch **`db-connector-creator`**
- **Storage/other connectors**: dispatch **`storage-connector-creator`**

**GATE: Do NOT proceed to Phase 3 until the connector is created** — public endpoints live inside the connector directory.

### Phase 3 — Build endpoints (API connectors only)

**Skip this phase entirely for database and other connector types.** These connectors do not have
pre-defined endpoints — their endpoints are schema/table combinations discovered at runtime.

For API connectors with endpoints to register:

1. **Research all endpoints in parallel**: For each endpoint, read the endpoint research brief
   at `${CLAUDE_PLUGIN_ROOT}/skills/connector-wizard/research-brief-endpoint.md`, fill in the details,
   and dispatch **`connector-researcher`** with it. All endpoint research agents can run in parallel.

2. **Deprecation filter**: After research completes, check each endpoint's `deprecated` field.
   - Skip deprecated endpoints silently — do NOT build them.
   - Inform the user which endpoints were skipped and why.
   - If the user explicitly asks to include a deprecated endpoint, build it and tag it as
     deprecated in the manifest (see `connector-scaffolding` for the manifest format).

3. **Create all endpoint files in parallel**: For each non-deprecated endpoint (plus any
   deprecated endpoints the user explicitly requested), dispatch **`endpoint-creator`**
   with the endpoint research results. All endpoint creators can run in parallel — they each
   create only their own endpoint JSON file under `definition/endpoints/`.

4. **After ALL endpoint-creators complete**, collect their results and update the following files
   yourself (the orchestrator handles this, not endpoint-creator):
   - **`CLAUDE.md`** — add all endpoints to the "Available Endpoints" table
   - **`AGENTS.md`** — keep identical to CLAUDE.md (apply the same changes)
   - **`README.md`** — add all endpoints to the "Available Endpoints" table
   - **`CHANGELOG.md`** — add entries for all new endpoints

### Phase 4 — Build manifest

Build `manifest.json` as the final assembly step. Read the `manifest-assembly` skill at
`${CLAUDE_PLUGIN_ROOT}/skills/manifest-assembly/SKILL.md` for the full specification.

1. **Read `connector.json`** — extract all `${placeholder}` tokens and categorize each by source.
2. **Read all endpoint files** in `definition/endpoints/` (API connectors only) — extract any
   `${placeholder}` tokens per endpoint.
3. **Build `manifest.json`** in `definition/` with the complete placeholder registry and endpoint
   index. Follow the manifest-assembly skill for structure, source categories, and examples.

This phase applies to **all connector types**:
- **API connectors**: manifest includes connector-level placeholders and all endpoint entries
- **Database/storage connectors**: manifest has empty `placeholders` and `endpoints` arrays

Do NOT manually bump the manifest `version` — a GitHub Action bumps it automatically when a PR
is merged, based on PR labels (`version:minor`, `version:patch`, `version:major`).

### Phase 5 — Validate (optional, requires ANALITIQ_API_KEY)

If the user provided an `ANALITIQ_API_KEY` (see Validation section below), validate the created
connector and endpoints against the Analitiq validation API. If all validations pass, add the
`validated` topic to the connector repo.

### Phase 6 — Contribute to Community (optional)

After all build and validation phases are complete, offer the user the option to contribute
their connector to the Analitiq community registry.

1. Ask the user: *"Would you like to contribute this connector to the Analitiq community
   registry? This will create a public repo on your GitHub account with a sanitized copy
   (no credentials or PII) and open a submission request in the registry."*

2. **If the user declines** — end the workflow normally. The connector remains local.

3. **If the user accepts** — dispatch the **`registry-contributor`** agent with the following
   context:
   - `slug` — the connector slug
   - `connector_name` — human-readable name
   - `connector_type` — `api`, `database`, or `other`
   - `auth_type` — the auth type used
   - `connector_descr` — short description
   - `validation_status` — `"validated"` if Phase 5 passed, `"not validated"` if skipped
   - `connector_path` — absolute path to the `{slug}/` directory

4. The `registry-contributor` agent handles: PII scanning, sanitized copy creation, GitHub
   repo creation under the user's account, push, and submission issue creation in
   `analitiq-dip-registry/connector-submissions`.

5. Report the submission issue URL back to the user. Let them know the connector will be
   reviewed by registry maintainers before being imported.

**Prerequisites:** The user must have GitHub CLI (`gh`) installed and authenticated. The
`registry-contributor` agent verifies this before proceeding.

---

## Connector Directory Structure

Each connector is stored in its own directory named `{slug}/` with this structure:

**API connectors** (with endpoints):
```
{slug}/
├── CLAUDE.md               # Agent reference for Claude Code (auth, endpoints, caveats)
├── AGENTS.md               # Agent reference for other frameworks (identical to CLAUDE.md)
├── README.md               # Human documentation (setup instructions, credentials)
├── CHANGELOG.md            # Version history
└── definition/             # Connector definition files (machine-consumed JSON)
    ├── connector.json      # Authentication details and connector definition
    ├── manifest.json       # Placeholder registry + endpoint index
    └── endpoints/          # Directory containing all endpoint JSON definitions
        ├── {endpoint_name}.json
        └── ...
```

**Database and other connectors** (no endpoints):
```
{slug}/
├── CLAUDE.md               # Agent reference for Claude Code (auth, caveats)
├── AGENTS.md               # Agent reference for other frameworks (identical to CLAUDE.md)
├── README.md               # Human documentation (setup instructions, credentials)
├── CHANGELOG.md            # Version history
└── definition/             # Connector definition files (machine-consumed JSON)
    ├── connector.json      # Authentication details and connector definition
    └── manifest.json       # Connector manifest (empty placeholders and endpoints arrays)
```

Database and other connectors do NOT have an `endpoints/` directory or endpoint JSON files.
Their "endpoints" (schema/table combinations) are specific to each deployment and discovered at runtime.

---

## Version Bumping — PR Labels

Version bumping happens automatically when a PR is merged, based on labels. Do NOT manually bump
the version in `definition/manifest.json` or `CHANGELOG.md` — a GitHub Action handles this on merge.

When creating a PR, apply the appropriate label:
- `version:minor` — new connector or new endpoints added (most common)
- `version:patch` — fixes to existing connector or endpoint definitions
- `version:major` — breaking changes to connector auth or structure

If no version label is applied, the version is not bumped.

---

## Validation — Optional but Recommended

If the user provided an `ANALITIQ_API_KEY`, validate all connector and endpoint JSON against the
Analitiq validation API. This catches subtle schema errors that agents may introduce.

Read `${CLAUDE_PLUGIN_ROOT}/skills/connector-wizard/validation-api.md` for the full validation protocol
(API key collection, endpoints, response formats, and the topic-tagging workflow).

---

## Important

- Be conversational but efficient. Don't overwhelm with questions — ask the most important ones first.
- If the user mentions a well-known system (Wise, Xero, Shopify, PostgreSQL, etc.), note that the Connector Research Agent can look up documentation automatically.
- You are the orchestrator. You gather requirements, check for duplicates, dispatch research and creation agents, and handle post-creation updates (manifest, docs). You do NOT create connector or endpoint JSON files yourself.
