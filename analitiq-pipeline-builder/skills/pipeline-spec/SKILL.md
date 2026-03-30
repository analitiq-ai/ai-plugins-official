---
name: pipeline-spec
disable-model-invocation: true
description: >
  Pipeline specification for creating pipeline configuration files. Contains the pipeline
  JSON format with connections, schedule, engine, and runtime configuration. This skill
  should be loaded when creating or modifying a pipeline definition.
---

# Pipeline Specification

## Pipeline JSON Structure

Streams are added by the wizard after all stream-builders complete.

```json
{
  "name": "Source to Destination",
  "description": "Pipeline description",
  "status": "draft",
  "connections": {
    "source": { "conn_1": null },
    "destinations": [{ "conn_2": null }]
  },
  "streams": [],
  "schedule": {
    "type": "manual"
  },
  "engine": {
    "vcpu": 1.0,
    "memory": 8192
  },
  "runtime": {
    "buffer_size": 5000,
    "batching": {
      "batch_size": 100,
      "max_concurrent_batches": 3
    },
    "logging": {
      "log_level": "INFO",
      "metrics_enabled": true
    },
    "error_handling": {
      "strategy": "dlq",
      "max_retries": 3,
      "retry_delay": 5
    }
  },
  "tags": []
}
```

## Connections

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | object | yes | Single source connection: `{ "conn_1": null }` |
| `destinations` | array | yes | One or more destination connections: `[{ "conn_2": null }]` |

Source must have exactly one connection. Destinations must have at least one.
Connection IDs are left null (populated server-side).

### Connection Ref Convention

- `conn_1` = source
- `conn_2` = first destination
- `conn_3` = second destination (if any)

## Schedule

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | yes | `"manual"`, `"interval"`, or `"cron"` |
| `timezone` | string | no | IANA timezone name (default: `"UTC"`) |
| `interval_minutes` | integer | conditional | Required when type is `"interval"` (min: 1) |
| `cron_expression` | string | conditional | Required when type is `"cron"` |

Default to `"manual"` unless the user specifies a schedule.

## Engine

Container resource allocation (consumed by AWS Batch):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vcpu` | number | `1.0` | vCPU allocation (min: 0.25) |
| `memory` | integer | `8192` | Memory in MB (min: 512) |

## Runtime

Pipeline execution behavior:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `buffer_size` | integer | `5000` | Record buffer size (min: 100) |
| `batching.batch_size` | integer | `100` | Batch size for processing |
| `batching.max_concurrent_batches` | integer | `3` | Max concurrent batches |
| `logging.log_level` | string | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logging.metrics_enabled` | boolean | `true` | Whether metrics collection is enabled |
| `error_handling.strategy` | string | `"dlq"` | `dlq`, `retry`, `fail`, `skip` |
| `error_handling.max_retries` | integer | `3` | Max retry attempts (0-100) |
| `error_handling.retry_delay` | integer | `5` | Retry delay in seconds |

Use defaults unless the user requests specific values.

## Key Rules

- `streams` array starts empty — populated by wizard after stream-builders complete
- `name` is required and must be non-empty
- Default status is `"draft"`
- Schedule, engine, and runtime use sensible defaults — only override if user specifies

## Output

Save the pipeline to:
```
pipelines/{pipeline-name}/pipeline.json
```

Create the streams subdirectory:
```
pipelines/{pipeline-name}/streams/
```
