---
name: pipeline-spec
disable-model-invocation: true
description: >
  Pipeline specification for assembling complete pipeline configuration files.
  Contains the pipeline JSON format with all sections: pipeline, connections, connectors,
  endpoints, and streams. This skill should be loaded when assembling or modifying a pipeline.
---

# Pipeline Specification

## Pipeline JSON Structure

```json
{
  "pipeline": {
    "pipeline_id": "uuid_v1",
    "org_id": "uuid",
    "name": "Source to Destination",
    "status": "active",
    "version": 1,
    "connections": {
      "source": { "conn_1": "source-connection-uuid" },
      "destinations": [{ "conn_2": "dest-connection-uuid" }]
    },
    "streams": ["stream-uuid_v1"],
    "schedule": {
      "type": "interval",
      "timezone": "UTC",
      "interval_minutes": "1440"
    },
    "engine": { "vcpu": 1, "memory": 8192 },
    "runtime": {
      "buffer_size": 5000,
      "batching": { "batch_size": 100, "max_concurrent_batches": 3 },
      "logging": { "log_level": "INFO", "metrics_enabled": true },
      "error_handling": { "strategy": "dlq", "max_retries": 3, "retry_delay": 5 }
    },
    "tags": []
  },
  "connections": [ ... ],
  "connectors": [
    { "connector_id": "uuid", "connector_name": "Name", "connector_type": "api", "slug": "slug" }
  ],
  "endpoints": [ ... ],
  "streams": [
    {
      "stream_id": "uuid_v1",
      "version": 1,
      "pipeline_id": "pipeline-uuid",
      "org_id": "uuid",
      "status": "draft",
      "is_enabled": true,
      "source": {
        "connection_ref": "conn_1",
        "endpoint_id": "source-endpoint-uuid_v1",
        "primary_key": ["id"],
        "replication": { "method": "full" }
      },
      "destinations": [{
        "connection_ref": "conn_2",
        "endpoint_id": "dest-endpoint-uuid_v1",
        "write": { "mode": "upsert" }
      }],
      "mapping": {
        "assignments": [ ... ],
        "source_to_generic": { ... },
        "generic_to_destination": { ... },
        "assignments_hash": "",
        "type_mapping_assignments_hash": ""
      }
    }
  ]
}
```

## Connection Ref Convention

- `conn_1` = source
- `conn_2` = first destination
- `conn_3` = second destination (if any)

## ID Conventions

- Pipeline ID: `{uuid}_v{version}` (e.g., `abc123_v1`)
- Stream ID: `{uuid}_v{version}`
- Endpoint ID in streams: `{uuid}_v{version}` (versioned reference)

## Cross-Reference Validation

1. Every `connection_ref` in streams matches a key in `pipeline.connections`
2. Every `endpoint_id` in streams exists in the `endpoints` array
3. Every `connection_id` in `pipeline.connections` exists in the `connections` array
4. Every `connector_id` in connections exists in the `connectors` array
5. Stream IDs listed in `pipeline.streams` match actual stream objects

## Default Test org_id

Use `d7a11991-2795-49d1-a858-c7e58ee5ecc6` for testing unless specified otherwise.

## Output

Save assembled pipeline to `pipelines/{pipeline_id}.json` (without the version suffix in filename).
