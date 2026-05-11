# Orchestration pipeline (full contract)

This file is the long-form contract referenced by `SKILL.md §Pipeline`.
The orchestrator runs 11 phases in order. Each phase declares its
preconditions, the agent invoked (if any), and the postconditions that
the next phase relies on.

| # | Phase | Agent | Postcondition |
|---|---|---|---|
| 0 | Pre-flight collision check | _orchestrator_ | No conflicting directories exist on disk. |
| 1 | Research | `pipeline-provider-researcher` | A `PipelineFacts` JSON object is captured (see `io-contracts.md`). |
| 2 | Connector download | `registry-browser` × 2 (parallel) | `connectors/{source}/` and `connectors/{destination}/` exist with `definition/connector.json` + (api only) `definition/endpoints/`. |
| 3 | Classify | _orchestrator_ | `schedule.type`, `replication.method`, `write.mode` resolved against closed enums. |
| 4 | Mint placeholder IDs | _orchestrator_ | Stable alias → versioned-UUID map exists for both connections and the pipeline. |
| 5 | Connections | `connection-creator` × N (parallel per side) | One `connections/{alias}/connection.json` plus `connections/{alias}/.secrets/credentials.json` per side, each validating against `connection/latest.json`. |
| 6 | Endpoint discovery | `private-endpoint-creator` × M (DB only) | `connections/{alias}/endpoints/*.json` for selected tables, each validating against `database-endpoint/latest.json`. |
| 7 | Pipeline shell | `pipeline-creator` | `pipelines/{alias}/pipeline.json` with `streams: []`, validating against `pipeline/latest.json`. |
| 8 | Streams | `stream-creator` × K (parallel) | `pipelines/{alias}/streams/{stream-alias}.json` per selected endpoint, each validating against `stream/latest.json`. |
| 9 | Stitch | _orchestrator_ | `pipeline.json#/streams` is populated with the K versioned stream IDs; bundle validates with `--bundle-root .`. |
| 10 | Validate | `pipeline-schema-validator` (looped, ≤ 5 passes) | Every artifact has zero `error`-severity findings. |
| 11 | Drift (optional) | `pipeline-drift-classifier` | A structural diff vs. `previous_release_path`; informational only. |

## Halt conditions

The orchestrator must halt (and surface a clear message) when:

- Phase 0 finds a conflicting directory.
- Phase 1's required inputs are missing (`source_connector_alias`,
  `destination_connector_alias`, `pipeline_alias`).
- Phase 2 cannot resolve a connector alias in the DIP registry.
- Phase 3's enum mappers fail to map an input (the user supplied
  something outside the closed set).
- Phase 5's `connection-creator` returns a structured refusal (e.g.
  unsupported auth type for the chosen connector).
- Phase 6's database introspection fails (credentials wrong, network
  unreachable). The orchestrator surfaces the underlying error verbatim
  and waits for the user to fix it.
- Phase 10 still has `error`-severity findings after 5 fix passes.

Halting means: do not write partial files, do not advance to a later
phase, and do not auto-retry without user input.

## Parallel dispatch

Phases that dispatch multiple agents in parallel (2, 5, 8) issue all
calls in a single message — multiple tool invocations in one turn — so
they run concurrently. Do not sequence them artificially.

## Fix-and-revalidate loop (phase 10)

For each artifact:

1. Run the validator.
2. If `passed: true`, accept and move on.
3. If `passed: false`, collect the findings and re-invoke the matching
   creator with the findings attached, asking it to fix exactly the
   reported errors (and only those — no opportunistic edits).
4. Re-validate. Increment the pass counter.
5. Stop after 5 passes regardless of state. If still failing, halt and
   surface the diagnostics.

The validator is stateless — pass count and discipline live here, not
in `scripts/validate_pipeline.py`.
