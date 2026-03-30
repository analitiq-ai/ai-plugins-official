# Analitiq Connector Builder Plugin

Claude Code plugin for creating data integration connectors and endpoints that comply with the [Analitiq Data Integration Protocols](https://github.com/analitiq-dip-registry) (DIP). Supports API (REST/HTTP), database (PostgreSQL, MySQL), and storage (S3, SFTP) systems.

## What It Does

The plugin interviews you about the target system, researches its documentation, and generates the full connector definition — no coding required. Connectors are published to the [`analitiq-dip-registry`](https://github.com/analitiq-dip-registry) GitHub org as individual repos named `connector-{slug}`.

**Usage:** Launch Claude Code and say *"I want to create a connector for [system name]"*

## Agent Chain

```
wizard (orchestrator)
  ├── connector-researcher        # Researches system docs (auth, endpoints, drivers)
  ├── api-connector-creator       # Builds API connector definitions
  ├── db-connector-creator        # Builds database connector definitions
  ├── storage-connector-creator   # Builds storage connector definitions
  └── endpoint-creator            # Builds API endpoint definitions
```

1. **wizard** — interviews the user, checks for duplicates in the registry, dispatches research and creation agents, collects results, and optionally validates
2. **connector-researcher** — researches official documentation for auth details, connection parameters, or endpoint schemas
3. **{type}-connector-creator** — builds the connector definition (`connector.json`, `manifest.json`, repo scaffolding, docs)
4. **endpoint-creator** — builds individual endpoint JSON files (API connectors only)

## Supported Connector Types

| Type | `connector_type` | Auth | Examples |
|------|-------------------|------|----------|
| API | `api` | `api_key`, `basic_auth`, `oauth2_authorization_code`, `oauth2_client_credentials`, `jwt` | Wise, Xero, Shopify |
| Database | `database` | `db` | PostgreSQL, MySQL, MongoDB |
| Storage | `other` | `credentials` | S3, SFTP |

## Placeholder Source Categories

Every `${placeholder}` in a connector definition is registered in `manifest.json` with a source category describing where the value comes from.

| Source | Description | Examples |
|--------|-------------|----------|
| `user_defined` | Values provided by the user via form fields or credential files | `api_key`, `username`, `password`, `site`, `company_domain` |
| `system_defined` | Values returned by the target system during authentication | `access_token`, `refresh_token`, `code` |
| `post_auth` | Values resolved via post-authentication steps | `tenant_id`, `server_url`, `session_token`, `account_id` |
| `protocol` | OAuth2/auth protocol parameters from app registration or flow setup | `client_id`, `client_secret`, `redirect_uri`, `state`, `code_verifier` |
| `derived` | Values computed from other placeholders | `basic_auth`, `base64_credentials`, `jwt_token`, `code_challenge` |

Derived placeholders include a `derived_from` field listing their input placeholders.

## Installation

```bash
claude plugin add ./analitiq-connector-builder
```

Or point Claude Code to the local directory:

```bash
claude --plugin-dir /path/to/analitiq-connector-builder
```

## Optional: Validation API

If you have an `ANALITIQ_API_KEY`, the plugin validates all generated JSON against the Analitiq validation API to ensure 100% compliance with the DIP schema. You can get a free key at [analitiq-app.com](https://analitiq-app.com).

## Links

- [Analitiq DIP Registry](https://github.com/analitiq-dip-registry) — all available connectors
- [Analitiq Cloud](https://analitiq-app.com) — managed data integration platform
- [Analitiq](https://analitiq.ai) — learn more

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.