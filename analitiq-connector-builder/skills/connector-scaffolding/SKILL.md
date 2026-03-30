---
name: connector-scaffolding
disable-model-invocation: true
description: >
  Common scaffolding templates shared by all connector creator agents.
  Contains templates for CLAUDE.md, AGENTS.md, README.md, CHANGELOG.md, and manifest.json,
  plus the common connector fields specification. This skill should be loaded by any agent
  that creates connector directory structures.
---

# Connector Scaffolding

## Supporting Files

- [spec-common-attributes.md](spec-common-attributes.md) — common connector fields shared by all connector types

## GitHub Registry

All connectors live in the public GitHub org: `https://github.com/analitiq-dip-registry`
Connectors are named `connector-{slug}`. Use the `connector-template` repo as the starting point
for new connectors: `https://github.com/analitiq-dip-registry/connector-template`

### Slug Naming for Multi-Auth Connectors

When an API supports multiple authentication methods, each method gets its own connector with an
auth-specific slug:

- Single auth method → `connector-{system}` (e.g., `connector-wise`)
- Multiple auth methods → `connector-{system}-{auth_suffix}` (e.g., `connector-shopify-oauth2`,
  `connector-shopify-api-key`)

Short suffixes: `oauth2`, `api-key`, `basic-auth`, `client-credentials`, `jwt`

All connectors for the same system share the same `connector_name`, `base_url`,
and endpoints — they differ in `slug`, `auth`, `form_fields`, and `headers`. This is likely to happen when a system offers multipe authentication methods.

## Common Connector Fields

Read `${CLAUDE_PLUGIN_ROOT}/skills/connector-scaffolding/spec-common-attributes.md` for the full
specification of common attributes shared by all connector types (connector_name,
connector_type, slug, form_fields, auth, etc.).

## Key Rules

- Every `${placeholder}` in headers, base_url, or auth operations must be registered in `manifest.json` with a source category.
- Root `headers` are for API data requests only — never sent to auth operation URLs.
- For OAuth2 connectors, `auth.token_exchange` must be a full object with `url`, `method`, `content_type`, and `body` — never a bare URL string.

## manifest.json

`manifest.json` is built by the `wizard` orchestrator as a final assembly step — not by
connector-creator agents. See the [manifest-assembly](../manifest-assembly/SKILL.md) skill for
the full specification (structure, placeholder registry, source categories, endpoint entries,
deprecation tagging).

> **Database and other connectors** do NOT have pre-defined endpoints. Their "endpoints" are
> schema/table combinations specific to each deployment and discovered at runtime. The manifest
> `endpoints` array stays empty, and no `endpoints/` directory is created.

## CLAUDE.md and AGENTS.md — Agent Reference Files

These two files are **identical** in content. `CLAUDE.md` is read by Claude Code, `AGENTS.md` is for
other agent frameworks. Always create both files with the same content, and keep them in sync when
updating. Use this template for both:

```markdown
---
name: {connector_name}
description: >
  {One-line description of what this connector integrates with}
type: {api|database|other}
---

# {Connector Name}

{Brief description of the system and what data it provides.}

## Authentication

{List each supported auth type. If the API supports multiple auth methods, document all of them.}

### {Auth Type 1} (e.g., OAuth2 Authorization Code)
- Client app required: {yes|no}
- Scopes: {list of required scopes, if applicable}
- Token expiry: {duration, if applicable}

### {Auth Type 2} (e.g., API Key)
- Header format: {e.g., "Authorization: Bearer ${api_key}"}

## Post-Auth Steps

{Document any steps required after authentication, such as tenant/org selection, server URL
discovery, etc. If none, state "None required."}

## Available Endpoints (API connectors only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| {path}   | {GET}  | {what it returns} |

> For database and other connectors, omit this section entirely. Their "endpoints" are schema/table
> combinations specific to each deployment and are not pre-defined.

## Rate Limits (API connectors only)

- {max_requests} requests per {time_window_seconds} seconds

## Caveats

{Any special behaviour, quirks, or limitations that agents should be aware of when using this
connector. For example: tenant-specific subdomains, non-standard pagination, required headers
beyond auth, etc.}
```

Update both CLAUDE.md and AGENTS.md when new endpoints are added by the endpoint-creator (API connectors only).

## README.md — Human Documentation

This file is for humans, including non-technical users who may be discovering this connector for the first
time. Use the template from `connector-template/README.md` as your starting point — copy it and fill in
the REPLACE placeholders with connector-specific information.

The README must include these fixed sections (already in the template — do NOT remove them):
- **What is this?** — explains what a connector is and how it fits into Analitiq
- **How to use this connector** — Analitiq Cloud and open-source options
- **For AI agents** — points to CLAUDE.md and AGENTS.md
- **Contributing** — how to improve the connector
- **Links** — API docs, Analitiq Cloud, analitiq-core

And these connector-specific sections (fill in from research):
- **Prerequisites** — what the user needs before connecting (API key, OAuth app, admin access, etc.)
- **Authentication** — plain-language explanation of how to authenticate, including step-by-step credential instructions
- **Available Endpoints** (API connectors only) — table with Endpoint, Method, and Description columns. Omit for database/other connectors.
- **Limitations** — rate limits, data freshness, sandbox vs production differences

## CHANGELOG.md — Version History

Track changes to the connector and its endpoints. Use this template:

```markdown
# Changelog

## [1.0.0] - {YYYY-MM-DD}

### Added
- Initial connector definition with {auth_type} authentication
- Endpoints: {list of initial endpoints} <- API connectors only; omit this line for database/other
```

## Directory Structure Output

### API connectors (with endpoints)
```
connector-{slug}/
├── CLAUDE.md               # Agent reference for Claude Code (auth, endpoints, caveats)
├── AGENTS.md               # Agent reference for other frameworks (identical to CLAUDE.md)
├── README.md               # Human documentation (setup instructions, credentials)
├── CHANGELOG.md            # Version history
└── definition/             # Connector definition files (machine-consumed JSON)
    ├── connector.json      # The connector definition with auth details
    ├── manifest.json       # Placeholder registry + endpoint index (built by wizard orchestrator)
    └── endpoints/          # Directory for endpoint definitions (API only)
```

### Database and other connectors (no `endpoints/` directory)
```
connector-{slug}/
├── CLAUDE.md               # Agent reference for Claude Code (auth, caveats)
├── AGENTS.md               # Agent reference for other frameworks (identical to CLAUDE.md)
├── README.md               # Human documentation (setup instructions, credentials)
├── CHANGELOG.md            # Version history
└── definition/             # Connector definition files (machine-consumed JSON)
    ├── connector.json      # The connector definition with auth details
    └── manifest.json       # Connector manifest (built by wizard orchestrator)
```
