# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This repository previously bundled the official Analitiq Claude Code plugins for building data integration connectors and pipelines (Analitiq Data Integration Protocols / DIP). **Both plugins have moved to their own repositories** and this repo no longer contains plugin code:

- **`analitiq-connector-builder`** → [analitiq-ai/claude-plugin-connector-creator](https://github.com/analitiq-ai/claude-plugin-connector-creator) — authors connector / endpoint / type-map documents against the published Analitiq schema contract.
- **`analitiq-pipeline-builder`** → [analitiq-ai/claude-plugin-pipeline](https://github.com/analitiq-ai/claude-plugin-pipeline) — builds pipelines by wiring pre-defined connectors from the DIP registry.

Do connector or pipeline work in the respective repository above; each carries its own `CLAUDE.md`, schema-contract references, and tests.

## Related repositories

- [Analitiq DIP Registry](https://github.com/analitiq-ai/analitiq-dip-registry) — catalog of connector definitions.
- [Published schema contracts](https://schemas.analitiq.ai) — the JSON Schemas both plugins validate against.
