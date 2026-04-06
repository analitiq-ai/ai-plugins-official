---
name: registry-submission
disable-model-invocation: true
description: >
  Reference data for contributing connectors to the Analitiq community registry.
  Contains PII/credential detection patterns, sanitization rules, GitHub operations
  reference, and the submission issue template. Loaded by the registry-contributor agent.
---

# Registry Submission

## Prerequisites

The user must have:

1. **GitHub CLI (`gh`)** installed and authenticated — verify with `gh auth status`
2. **Permission to create public repos** on their GitHub account
3. **Internet access** to push to GitHub and open issues

If `gh auth status` fails, instruct the user to run `gh auth login` and stop the workflow.

---

## PII and Credential Detection

Before publishing any connector files, scan **every file** in the `{slug}/` directory for
personally identifiable information (PII) and hardcoded credentials. Connector definitions use
`${placeholder}` syntax for credential slots — the risk is that real values were accidentally
hardcoded instead.

### What to Scan

Scan all files in the connector directory:
- `definition/connector.json` — highest risk (contains auth config, headers, URLs)
- `definition/manifest.json` — lower risk but check placeholder values
- `definition/endpoints/*.json` — check for hardcoded tokens in headers or URL parameters
- `CLAUDE.md`, `AGENTS.md`, `README.md`, `CHANGELOG.md` — check examples and descriptions

### Detection Patterns

#### Category 1 — Hardcoded Credentials in JSON

These patterns indicate real credential values where `${placeholder}` should be used:

| Pattern | Description | Example Match |
|---------|-------------|---------------|
| `sk-[a-zA-Z0-9]{20,}` | Secret keys (Stripe, OpenAI, etc.) | `sk-proj-abc123def456...` |
| `pk_[a-zA-Z0-9]{20,}` | Public/publishable keys | `pk_live_abc123...` |
| `Bearer [a-zA-Z0-9_\-\.]{20,}` | Bearer tokens (not `${placeholder}`) | `Bearer ya29.a0AfH6SM...` |
| `eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+` | JWT tokens | `eyJhbGciOi...` |
| `xox[bspr]-[a-zA-Z0-9\-]{10,}` | Slack tokens | `xoxb-123-456-abc` |
| `ghp_[a-zA-Z0-9]{36}` | GitHub personal access tokens | `ghp_abc123...` |
| `AKIA[0-9A-Z]{16}` | AWS access key IDs | `AKIAIOSFODNN7EXAMPLE` |
| `[a-f0-9]{32,64}` in header values or `default` fields | Hex-encoded API keys/secrets | `a1b2c3d4e5f6...` |
| `[A-Za-z0-9+/]{40,}={0,2}` in header values or `default` fields | Base64-encoded secrets | `dGhpcyBpcyBh...` |

**Where to look in JSON:**
- `headers` object values (e.g., `"Authorization": "Bearer REAL_TOKEN"`)
- `form_fields[].default` values
- `auth.token_exchange.body` or `auth.refresh.body` containing literal tokens
- `base_url` containing literal API keys as query parameters

#### Category 2 — Embedded Credentials in URLs

| Pattern | Description |
|---------|-------------|
| `https?://[^:]+:[^@]+@` | URL with embedded `user:password` |
| `[?&](api_key\|token\|key\|secret\|password)=[a-zA-Z0-9_\-]{8,}` | URL with credential query params |

#### Category 3 — User-Specific Values

| Pattern | Where | Description |
|---------|-------|-------------|
| Subdomain in `base_url` that should be parameterized | `connector.json` | e.g., `https://acme.zendesk.com` instead of `https://${subdomain}.zendesk.com` |
| Real email addresses | Any `.md` file | e.g., `john@acme.com` in README examples |
| Internal/private hostnames or IPs | Any file | e.g., `192.168.1.50`, `db.internal.acme.com` |

#### Category 4 — Documentation Files

| Pattern | Where | Description |
|---------|-------|-------------|
| Real API keys in code examples | `README.md` | e.g., `curl -H "Authorization: Bearer sk-real-key"` |
| Real company/org names in examples | `README.md`, `CLAUDE.md` | When they reveal the user's identity |
| Real account IDs, tenant IDs | Any `.md` file | e.g., specific Xero tenant UUID in examples |

### False Positives — Do NOT Flag

- **`${placeholder}` syntax** — these are template variables, not real values (e.g., `${api_key}`, `${access_token}`)
- **Official API documentation URLs** — e.g., `https://developer.xero.com`, `https://api.wise.com`
- **Standard example values** — e.g., `example.com`, `test@example.com`, `localhost`
- **UUIDs in schema definitions** — e.g., `connector_id` format examples using random UUIDs
- **Port numbers** — e.g., `5432`, `3306`, `27017` (standard database ports)
- **Analitiq test org_id** — `d7a11991-2795-49d1-a858-c7e58ee5ecc6` (this is a known safe value)

---

## Sanitization Rules

When PII or credentials are found:

1. **Present each finding** to the user with file path, line/field, matched value, and the
   pattern category. Let the user confirm or dismiss each finding.
2. **Never auto-redact** — always get user confirmation before modifying any value.
3. **Apply replacements** to the **copy only** (see Clean Copy Strategy below).

### Replacement Table

| Category | Replacement |
|----------|-------------|
| API keys / secret keys | `YOUR_API_KEY` |
| Bearer tokens | `${access_token}` (use the standard placeholder) |
| JWT tokens | `YOUR_JWT_TOKEN` |
| AWS access keys | `YOUR_AWS_ACCESS_KEY_ID` |
| Slack tokens | `YOUR_SLACK_TOKEN` |
| GitHub tokens | `YOUR_GITHUB_TOKEN` |
| Passwords in URLs | `YOUR_PASSWORD` |
| User-specific subdomains | `${subdomain}` or `your-subdomain` (in docs) |
| Email addresses | `user@example.com` |
| Internal hostnames/IPs | `your-host.example.com` |
| Tenant/account IDs | `YOUR_TENANT_ID` or `${tenant_id}` |

---

## Clean Copy Strategy

If any PII or credentials are confirmed by the user:

1. **Copy** the entire `{slug}/` directory to `{slug}-submission/` in the same parent directory.
2. **Apply all confirmed redactions** to files in `{slug}-submission/` only — the original
   `{slug}/` directory is never modified.
3. **Use `{slug}-submission/`** as the source for the GitHub push.

If no PII or credentials are found (clean scan):

1. **Use the original `{slug}/` directory** directly — no copy needed.
2. Confirm with the user before proceeding to the GitHub push.

If `{slug}-submission/` already exists from a previous run, ask the user whether to overwrite
or abort.

---

## GitHub Operations

### Step 1 — Verify Authentication

```bash
gh auth status
```

If this fails, tell the user to authenticate and stop the workflow:
> "GitHub CLI is not authenticated. Please run `gh auth login` to authenticate, then try again."

### Step 2 — Get GitHub Username

```bash
gh api user --jq '.login'
```

Store this as `{username}` for subsequent steps.

### Step 3 — Create Repository

Create a public repo under the user's GitHub account:

```bash
gh repo create {slug} --public \
  --description "Analitiq DIP connector for {system} — {short description}. Community submission." \
  --clone=false
```

If the repo already exists, ask the user whether to use the existing repo or choose a
different name.

### Step 4 — Initialize and Push

Use the clean directory (either `{slug}-submission/` or `{slug}/`):

```bash
cd {source_directory}
git init
git add .
git commit -m "Initial connector definition for {system}"
git branch -M main
git remote add origin https://github.com/{username}/{slug}.git
git push -u origin main
```

### Step 5 — Open Submission Issue

```bash
gh issue create --repo analitiq-dip-registry/connector-submissions \
  --title "New connector submission: {slug}" \
  --body "$(cat <<'EOF'
{issue body from template below}
EOF
)"
```

If the issue creation fails (e.g., the `connector-submissions` repo doesn't exist or doesn't
allow external issues), provide the user with the issue body as text and suggest they open it
manually.

### Step 6 — Cleanup (Optional)

If a `{slug}-submission/` copy was created, offer to remove it:
> "The sanitized copy at `{slug}-submission/` is no longer needed. Would you like me to remove it?"

---

## Submission Issue Template

Use this template for the GitHub issue body. Fill in all `{placeholders}` from the connector
context passed by the connector-wizard.

```markdown
## Connector Submission

### Connector Details
- **Name:** {connector_name}
- **Slug:** {slug}
- **Type:** {connector_type}
- **Auth:** {auth_type}
- **Description:** {connector_descr}

### Source Repository
https://github.com/{username}/{slug}

### Validation Status
{One of: "Validated against Analitiq schema API" | "Not validated (no API key provided)"}

### Endpoints (API connectors only)
| Endpoint | Method | Description |
|----------|--------|-------------|
| {path}   | {method} | {description} |

> For database/storage connectors, omit this table — they do not have pre-defined endpoints.

### Recommended Registry Metadata

**Repository description:**
```
Analitiq DIP connector for {system} — {short description}. Built for AI-driven data integration pipelines.
```

**Topics:**
`analitiq`, `data-pipeline`, `dip`, `data-integrations`, `connector`, {type_topic}, {system_slug}

### Sanitization
{One of: "No PII or credentials detected — original files submitted as-is." | "PII/credentials were detected and removed before submission. See details below."}

{If sanitized, list what was redacted:}
{- Replaced hardcoded API key in connector.json headers with ${placeholder}}
{- Replaced real email in README.md examples with user@example.com}

### Checklist
- [ ] Connector JSON schema review
- [ ] Documentation review (README, CLAUDE.md)
- [ ] Import to registry org
- [ ] Set repository description and topics

---
*Submitted via analitiq-connector-builder plugin*
```

---

## Registry Metadata Reference

When populating the submission issue, use these rules for recommended metadata:

### Repository Description Template

```
Analitiq DIP connector for {system} — {short description}. Built for AI-driven data integration pipelines.
```

### Repository Topics

**Mandatory topics** (always included):
`analitiq`, `data-pipeline`, `dip`, `data-integrations`, `connector`

**Type-specific topic** (based on `connector_type`):
- `api` connectors → add `api`
- `database` connectors → add `database`
- `other` connectors → no additional type topic

**System name topic** (always included):
Add the system slug as a topic, e.g., `postgresql`, `hubspot`, `pipedrive`, `wise`
