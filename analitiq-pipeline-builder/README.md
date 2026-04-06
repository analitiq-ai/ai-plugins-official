# Analitiq Pipeline Builder Plugin

Claude Code plugin for building data integration pipelines using pre-defined connectors from the [Analitiq DIP Registry](https://github.com/analitiq-dip-registry). Does **not** create connectors — only downloads and wires them into complete pipelines.

## What It Does

The plugin interviews you about the source and destination systems, downloads the matching connectors from the registry, creates connections with credentials, discovers database endpoints if needed, and builds the pipeline with individually streamed endpoint mappings.

**Usage:** Launch Claude Code and say *"Build a pipeline from [source] to [destination]"*

## Agent Chain

```
pipeline-wizard (orchestrator)
  ├── registry-browser              # Downloads connectors from the DIP registry
  ├── connection-creator            # Creates connections + .secrets templates
  ├── private-endpoint-creator      # DB only: discovers schemas/tables from live connection
  ├── pipeline-builder              # Creates pipeline JSON shell
  └── stream-builder × N            # Builds individual streams with field mapping (parallel)
```

Phases are strictly sequential with gates:

1. **registry-browser** — downloads source + destination connectors (parallel)
2. **connection-creator** — creates connection JSON + `.secrets/` templates (parallel per side)
3. **private-endpoint-creator** — DB connections only: connects to database, discovers schemas/tables, creates endpoint files in the connection directory
4. **pipeline-wizard interviews** — presents available endpoints, user selects which to stream
5. **pipeline-builder** — creates pipeline JSON shell with connections and defaults
6. **stream-builder × N** — builds one stream per selected endpoint with field mapping (parallel)
7. **pipeline-wizard collects** — adds stream references to pipeline

## Installation

```bash
claude plugin add ./analitiq-pipeline-builder
```

Or point Claude Code to the local directory:

```bash
claude --plugin-dir /path/to/analitiq-pipeline-builder
```

## Links

- [Analitiq DIP Registry](https://github.com/analitiq-dip-registry) — all available connectors
- [Analitiq Cloud](https://analitiq-app.com) — managed data integration platform
- [Analitiq](https://analitiq.ai) — learn more

## License

Apache 2.0 — see [LICENSE](LICENSE) for details.
