# `engine` and `runtime` blocks

Both are optional with documented defaults. Author them only when the
user has a specific reason to deviate.

## `engine`

```jsonc
{
  "engine": {
    "vcpu": 1,        // default 1.0; minimum 0.5
    "memory": 8192    // MB; default 8192; minimum 1024
  }
}
```

The minimums (`vcpu >= 0.5`, `memory >= 1024`) reserve a 0.25 vCPU /
512 MB sidecar baseline so the engine container always has at least the
runtime floor after subtracting the destination container.

## `runtime`

```jsonc
{
  "runtime": {
    "buffer_size": 5000,           // default 5000; minimum 100
    "batching": {
      "batch_size": 100,           // default 100; range [1, 100000]
      "max_concurrent_batches": 3  // default 3; range [1, 100]
    },
    "logging": {
      "log_level": "INFO",         // default INFO; one of DEBUG/INFO/WARNING/ERROR/CRITICAL
      "metrics_enabled": true      // default true
    },
    "error_handling": {
      "strategy": "dlq",           // default dlq; one of fail/dlq/skip
      "max_retries": 3,            // default 3; range [0, 5]
      "retry_delay_seconds": 5     // required when max_retries > 0; omit/0 when max_retries == 0
    }
  }
}
```

## `error_handling` rules

The schema's `allOf/if-then-else` for `error_handling`:

- If `max_retries == 0`, then `retry_delay_seconds` must be omitted or
  zero. Non-zero delay with no retries is incoherent.
- If `max_retries > 0`, then `retry_delay_seconds` must be present and
  positive. Otherwise the retry loop has no wait, which the engine
  rejects.

The `runtime-ranges` Layer 2 validator enforces both rules.

## Per-destination override

Individual streams can override `runtime.batching` on a per-destination
basis via `stream.destinations[].execution.{batch_size,max_concurrent_batches}`.
See `stream-spec/spec-destinations.md`. The pipeline-level values are
defaults; stream-level overrides win.
