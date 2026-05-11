# `schedule` block

Default if omitted: `{type: "manual", timezone: "UTC"}`.

## `type: manual`

```jsonc
{"type": "manual", "timezone": "UTC"}
```

Must omit `interval_minutes` and `cron_expression`. Runs only on
explicit user trigger.

## `type: interval`

```jsonc
{"type": "interval", "timezone": "UTC", "interval_minutes": 60}
```

Requires `interval_minutes` (positive integer). Must omit
`cron_expression`. Minimum recommended interval is engine-dependent;
the schema only requires positivity.

## `type: cron`

```jsonc
{"type": "cron", "timezone": "Europe/Berlin", "cron_expression": "cron(0 2 * * ? *)"}
```

Requires `cron_expression` matching `^cron\(.+\)$` (AWS EventBridge
syntax). Must omit `interval_minutes`. The schema check is coarse —
full validity of the inner spec is the scheduler's responsibility, not
the plugin's.

## `timezone`

A valid IANA timezone name (e.g., `UTC`, `Europe/Berlin`, `America/New_York`).
The validator parses this with `zoneinfo.ZoneInfo` — anything Python's
tzdata rejects, the plugin rejects.

## Status interaction

`schedule` is **declarative**; the pipeline's `status` controls
whether the scheduler actually picks it up:

| `status` | scheduled execution |
|---|---|
| `draft` | disabled |
| `active` | enabled (subject to stream-side runnability) |
| `inactive` | disabled |

See `spec-streams-and-status.md`.
