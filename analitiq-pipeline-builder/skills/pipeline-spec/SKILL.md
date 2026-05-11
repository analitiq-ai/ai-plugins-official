---
name: pipeline-spec
description: Pipeline authoring vocabulary — connections refs, schedule, engine, runtime, streams, status. Loaded by pipeline-creator only. Not invoked directly by users.
disable-model-invocation: true
---

# pipeline-spec

This skill is loaded by `pipeline-creator` when authoring a pipeline
document conforming to `https://schemas.analitiq.ai/pipeline/latest.json`.

## Required reading (load on demand)

- `spec-connections.md` — versioned ID refs for source + destinations.
- `spec-schedule.md` — manual / interval / cron with IANA timezone.
- `spec-engine-runtime.md` — vcpu/memory floor, batching, logging, error_handling.
- `spec-streams-and-status.md` — stream pinning rules and lifecycle gating.
- At least one of `examples/*.example.json` for the schedule style you're authoring.

## What this skill covers

- Top-level shape: `$schema`, `alias`, `display_name`, `description`,
  `status`, `connections`, `streams`, `schedule`, `engine`, `runtime`,
  `tags`.
- Defaults the registry applies when fields are omitted.
- Which fields the **plugin** must omit because they are server-managed
  (see `../pipeline-builder/references/reserved-fields.md`).

## What this skill does NOT cover

- Stream bodies — see `stream-spec`.
- Connection bodies — see `connection-spec`.
- Database endpoint bodies — see `endpoint-spec`.
- Connector bodies — that's the `analitiq-connector-builder` plugin.

## Output rules

Every authored document must:

1. Declare `$schema: "https://schemas.analitiq.ai/pipeline/latest.json"`.
2. Include `alias` (`[a-z0-9][a-z0-9_-]*`) and a non-empty `connections`
   object.
3. Omit every reserved field (`pipeline_id`, `version`,
   `pipeline_schema_version`, `org_id`, `created_at`, `updated_at`).
4. Use **versioned** connection IDs in `connections.source` and
   `connections.destinations[]` — `<uuid>_v<positive integer>`.
5. Use **versioned** stream IDs in `streams[]`.
6. Pass `python scripts/validate_pipeline.py --entity pipeline
   --document <path>` with zero error findings.
