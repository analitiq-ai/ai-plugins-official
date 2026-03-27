# Analitiq Plugins for Claude Code

Official [Analitiq](https://analitiq.ai) plugins for Claude Code. Build data integration connectors and pipelines that comply with Analitiq Data Integration Protocols (DIP).

## Plugins

### analitiq-plugin-connector-builder

Creates new connectors and endpoints for the [Analitiq DIP Registry](https://github.com/analitiq-dip-registry). Supports API (REST/HTTP), database (PostgreSQL, MySQL), and storage (S3, SFTP) integrations. The plugin interviews you about the target system, researches its API documentation, and generates the full connector definition — no coding required.

**Usage:** Launch Claude Code and say *"I want to create a connector for [system name]"*

### analitiq-plugin-dataflow

Builds data integration pipelines using pre-defined connectors from the DIP registry. Handles the full flow: downloading connectors, collecting credentials, mapping fields between source and destination, and assembling the pipeline.

**Usage:** Launch Claude Code and say *"I need to move data from [source] to [destination]"*

## Installation

These plugins are not yet available in the Claude Marketplace. To install manually:

1. Clone this repository:
   ```bash
   git clone https://github.com/analitiq-dip-registry/ai-plugins-official.git
   ```

2. Install the plugin you need by pointing Claude Code to the local directory:
   ```bash
   claude plugin add ./ai-plugins-official/analitiq-plugin-connector-builder
   claude plugin add ./ai-plugins-official/analitiq-plugin-dataflow
   ```

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