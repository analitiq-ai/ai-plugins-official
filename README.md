# Analitiq Plugins for Claude Code

> **The plugins have moved.** This repository previously bundled the official Analitiq Claude Code plugins. Each now lives in its own repository:
>
> | Plugin | Repository | What it does |
> |---|---|---|
> | **analitiq-connector-builder** | [analitiq-ai/claude-plugin-connector-creator](https://github.com/analitiq-ai/claude-plugin-connector-creator) | Creates connectors + endpoints for the DIP Registry. |
> | **analitiq-pipeline-builder** | [analitiq-ai/claude-plugin-pipeline](https://github.com/analitiq-ai/claude-plugin-pipeline) | Builds pipelines by wiring pre-defined connectors. |

## How Analitiq works

Analitiq is a set of open-source tools for connecting APIs, databases, and storage systems — no coding required.

| Repository | What it does |
|---|---|
| **[Connector plugin](https://github.com/analitiq-ai/claude-plugin-connector-creator)** | Claude Code plugin that builds connectors through conversation. |
| **[Pipeline plugin](https://github.com/analitiq-ai/claude-plugin-pipeline)** | Claude Code plugin that assembles pipelines from registry connectors. |
| **[DIP Registry](https://github.com/analitiq-dip-registry)** | Open catalog of ready-made connector definitions for common systems. |
| **[Core Engine](https://github.com/analitiq-ai/analitiq-core)** | Runs the pipelines — reads from sources, transforms data, writes to destinations. |

**Use the plugins** to create connectors and assemble pipelines. **Connectors** live in the registry. **The engine** executes the pipelines. Or skip the setup and use **[Analitiq Cloud](https://analitiq-app.com)** for a fully managed experience.

Learn more at [analitiq.ai](https://analitiq.ai).

## Installation

Install each plugin from its own repository (see the table above). From a local clone of either repo:

```bash
claude plugin add ./claude-plugin-connector-creator
claude plugin add ./claude-plugin-pipeline
```

## Links

- [Analitiq](https://analitiq.ai) — learn more about Analitiq
- [Analitiq Cloud](https://analitiq-app.com) — managed data integration platform
- [Analitiq DIP Registry](https://github.com/analitiq-dip-registry) — all available connectors

## License

See [LICENSE](LICENSE) for details.
