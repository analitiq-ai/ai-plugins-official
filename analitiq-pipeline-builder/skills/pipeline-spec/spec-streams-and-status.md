# `streams` and `status`

## `streams`

An array of **stream UUIDs**. Each entry is the `stream_id` of a stream
defined in a sibling `streams/<stream-slug>.json` file.

```jsonc
{
  "streams": [
    "22222222-2222-4222-8222-222222222222",
    "23232323-2323-4323-8323-232323232323"
  ]
}
```

Rules:

- UUIDs are unique within the array (`uniqueItems: true` in the schema).
- Each referenced stream's `pipeline_id` must equal this pipeline's
  `pipeline_id`. The `pipeline-stream-consistency` Layer 2 validator
  enforces this when `--bundle-root` is supplied.
- An empty `streams` array is permitted in `draft` or `inactive`
  status. Only `status: active` requires non-empty `streams` (see
  `status-lifecycle` validator below).

## `status`

| value | semantics |
|---|---|
| `draft` (default) | Editable. Not scheduled. `streams` may be empty. |
| `active` | Scheduled (subject to `schedule.type`). Requires non-empty `streams` AND at least one referenced stream with its own `status: "active"`. |
| `inactive` | Paused. Not scheduled. `streams` may be empty. |

`status: active` requires runnable streams. The `status-lifecycle`
Layer 2 validator emits an error when an `active` pipeline has no
streams, and a warning when called without `--bundle-root` (because it
can't read stream files to verify per-stream status).

## Authoring sequence

The orchestrator authors the pipeline shell with `streams: []` in phase
6, then stitches the stream UUIDs back in phase 8 after the parallel
`stream-creator` dispatch returns each new `stream_id`. The shell starts
in `status: draft`. Promotion to `active` happens later (typically when
the user submits the pipeline to the registry).
