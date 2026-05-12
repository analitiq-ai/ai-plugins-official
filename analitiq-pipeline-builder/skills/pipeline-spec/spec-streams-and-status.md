# `streams` and `status`

## `streams`

An array of **stream aliases**. Each entry references a stream defined
in a sibling `streams/{stream-alias}.json` file.

```jsonc
{
  "streams": [
    "wise_users_to_postgresql_users",
    "wise_transfers_to_postgresql_transfers"
  ]
}
```

Rules:

- Aliases are unique within the array (`uniqueItems: true` in the
  schema).
- Each referenced stream's `pipeline_id` must equal this pipeline's
  `alias`. The `pipeline-stream-consistency` Layer 2 validator enforces
  this when `--bundle-root` is supplied.
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
phase 6, then stitches the stream aliases back in phase 8 after the
parallel `stream-creator` dispatch returns. The shell starts in
`status: draft`. Promotion to `active` happens later (typically when
the user submits the pipeline to the registry).