# Analitiq Plugins for Claude Code

Official [Analitiq](https://analitiq.ai) plugins for Claude Code. Build data integration connectors and pipelines that comply with Analitiq Data Integration Protocols (DIP).

## Plugins

### analitiq-connector-builder

Creates new connectors and endpoints for the [Analitiq DIP Registry](https://github.com/analitiq-dip-registry). Supports API (REST/HTTP), database (PostgreSQL, MySQL), and storage (S3, SFTP) integrations. The plugin interviews you about the target system, researches its API documentation, and generates the full connector definition — no coding required.

**Usage:** Launch Claude Code and say *"I want to create a connector for [system name]"*

### analitiq-plugin-dataflow

Builds data integration pipelines using pre-defined connectors from the DIP registry. Handles the full flow: downloading connectors, collecting credentials, mapping fields between source and destination, and assembling the pipeline.

**Usage:** Launch Claude Code and say *"I need to move data from [source] to [destination]"*

Supported Authentication methods:
```text
  ┌─────┬───────────────────────────┬─────────────────────────────────────────┐
  │  #  │         auth.type         │                Use Case                 │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 1   │ api_key                   │ API key or token                        │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 2   │ basic_auth                │ Username + password                     │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 3   │ oauth2_authorization_code │ Browser-based OAuth flow                │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 4   │ oauth2_client_credentials │ Client ID/secret token exchange         │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 5   │ jwt                       │ Private key + issuer + key ID           │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 6   │ db                        │ Database host/port/user/password        │
  ├─────┼───────────────────────────┼─────────────────────────────────────────┤
  │ 7   │ credentials               │ Storage-specific credentials (S3, SFTP) │
  └─────┴───────────────────────────┴─────────────────────────────────────────┘
```

## Installation

These plugins are not yet available in the Claude Marketplace. To install manually:

1. Clone this repository:
   ```bash
   git clone https://github.com/analitiq-dip-registry/ai-plugins-official.git
   ```

2. Install the plugin you need by pointing Claude Code to the local directory:
   ```bash
   claude plugin add ./ai-plugins-official/analitiq-connector-builder
   claude plugin add ./ai-plugins-official/analitiq-plugin-dataflow
   ```
   or
   
   ```
   claude --plugin-dir /path/to/plugin-a --plugin-dir /path/to/plugin-b
   ````

3. Verify the plugin is installed:
   ```bash
   claude plugin list
   ```

## Links

- [Analitiq](https://analitiq.ai) — learn more about Analitiq
- [Analitiq Cloud](https://analitiq-app.com) — managed data integration platform
- [Analitiq DIP Registry](https://github.com/analitiq-dip-registry) — all available connectors

## License

See [LICENSE](LICENSE) for details.
