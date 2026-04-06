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

Streams are added by the pipeline-wizard after all stream-builders complete.

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
      "batch_size": 3000,
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
| `batching.batch_size` | integer | `3000` | Batch size for processing |
| `batching.max_concurrent_batches` | integer | `3` | Max concurrent batches |
| `logging.log_level` | string | `"INFO"` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `logging.metrics_enabled` | boolean | `true` | Whether metrics collection is enabled |
| `error_handling.strategy` | string | `"dlq"` | `dlq`, `retry`, `fail`, `skip` |
| `error_handling.max_retries` | integer | `3` | Max retry attempts (0-100) |
| `error_handling.retry_delay` | integer | `5` | Retry delay in seconds |

Use defaults unless the user requests specific values or batch size derivation (below)
produces a different value.

## Batch Size Derivation

Rather than always using the default `batch_size` of 3000, derive it from the source and
destination connector capabilities. Read both connector definitions before setting runtime
defaults.

### Source constraints

| Source type | Where to look | Constraint |
|-------------|---------------|------------|
| API | `endpoint.pagination.params.limit_param` default / max page size | Batch size should not exceed the API's max page size — fetching larger batches than a single page is wasteful since the engine must paginate anyway |
| API | `connector.requests_per_second` | High batch sizes with tight rate limits cause throttling; keep `max_concurrent_batches` × requests-per-batch ≤ `max_requests` per `time_window_seconds` |
| Database | No explicit limit | Databases handle large reads well; default (3000) or higher is fine |

### Destination constraints

| Destination type | Constraint |
|------------------|------------|
| Database | Most databases handle batch inserts of 1000–5000 rows efficiently. Use the default unless the user specifies otherwise. |
| API | If the destination is an API with rate limits, cap `batch_size` to avoid exceeding `requests_per_second` |
| Storage (S3/SFTP) | Batch size is less critical — files are written as complete objects. Default is fine. |

### Derivation rules

1. **API → Database:** Set `batch_size` to the API's max page size (from pagination config).
   If the endpoint has no pagination, use the default.
2. **Database → Database:** Use the default (3000).
3. **API → API:** Set `batch_size` to the minimum of source page size and destination rate
   limit capacity.
4. **Database → API:** Cap `batch_size` at the destination API's rate limit capacity.
5. **Per-stream override:** When source endpoints have different page sizes, the pipeline-wizard or
   stream-builder can set `destination.batching.batch_size` on individual streams to override
   the pipeline default.

### Example

A source API with `pagination.params.limit_param` defaulting to 250 and
`requests_per_second: { "max_requests": 60, "time_window_seconds": 60 }`:

```json
{
  "runtime": {
    "buffer_size": 5000,
    "batching": {
      "batch_size": 250,
      "max_concurrent_batches": 3
    }
  }
}
```

## Key Rules

- `streams` array starts empty — populated by pipeline-wizard after stream-builders complete
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
