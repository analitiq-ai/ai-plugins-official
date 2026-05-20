---
name: pipeline-spec
description: Pipeline authoring vocabulary — connection refs, schedule, engine, runtime, streams, status. Loaded by pipeline-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# pipeline-spec

This skill is loaded by `pipeline-creator` when authoring a pipeline
document conforming to `https://schemas.analitiq.ai/pipeline/latest.json`.

## Required reading (load on demand)

- `spec-connections.md` — UUID refs for source + destinations.
- `spec-schedule.md` — manual / interval / cron with IANA timezone.
- `spec-engine-runtime.md` — vcpu/memory floor, batching, logging, error_handling.
- `spec-streams-and-status.md` — stream pinning rules and lifecycle gating.
- At least one of `examples/*.example.json` for the schedule style you're authoring.

## What this skill covers

- Top-level shape: `$schema`, `pipeline_id`, `display_name`, `description`,
  `status`, `connections`, `streams`, `schedule`, `engine`, `runtime`,
  `tags`.
- Defaults the registry applies when fields are omitted.

## What this skill does NOT cover

- Stream bodies — see `stream-spec`.
- Connection bodies — see `connection-spec`.
- Database endpoint bodies — see `endpoint-spec`.
- Connector bodies — that's the `analitiq-connector-builder` plugin.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/pipeline/latest.json"`.
2. Include a non-empty `connections` object (the only schema-required
   field at the pipeline level). Author `pipeline_id` as an RFC-4122 UUID
   the plugin generates (plugin convention; the schema permits omission
   and the service will assign one on ingest). The directory name
   (`pipelines/<slug>/`) stays human-readable and is independent of the
   UUID.
3. Use **connection UUIDs** in `connections.source` and
   `connections.destinations[]`. Plugin convention is to set these to
   the `connection_id` of the corresponding `connections/<slug>/connection.json`
   files; the `pipeline-stream-consistency` validator enforces this on
   `--bundle-root`. The schema itself accepts any non-empty string.
4. Use **stream UUIDs** in `streams[]` — plugin convention is to set
   these to the `stream_id` of the corresponding `streams/<slug>.json`
   files.
5. Pass `python scripts/validate_pipeline.py --entity pipeline
   --document <path>` with zero error findings.
