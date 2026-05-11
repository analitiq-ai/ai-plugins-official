# `streams` and `status`

## `streams`

An array of **versioned stream IDs** (`<uuid>_v<n>`). Each entry pins
the pipeline at a specific stream version.

```jsonc
{
  "streams": [
    "10000000-0000-4000-8000-000000000010_v3",
    "10000000-0000-4000-8000-000000000011_v1"
  ]
}
```

Rules:

- At most one version per stream base UUID. You cannot pin both
  `<base>_v1` and `<base>_v3` in the same pipeline.
- Each referenced stream's `pipeline_id` (base UUID) must equal the
  pipeline's base UUID. The `pipeline-stream-consistency` Layer 2
  validator enforces this when `--bundle-root` is supplied.
- Empty array is allowed; required when the pipeline is in `draft` or
  `inactive` status.

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

The orchestrator authors the pipeline shell with `streams: []` in
phase 7, then stitches the stream IDs back in phase 9 after the parallel
`stream-creator` dispatch returns. The shell starts in `status: draft`.
Promotion to `active` happens later (typically when the user submits
the pipeline to the registry).
