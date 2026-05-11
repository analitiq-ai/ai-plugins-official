# Closed-enum mappers

The orchestrator runs these mappers inline at phase 3. Every mapper is
**fail-closed**: if the user input doesn't match an entry, halt and ask.

## ScheduleTypeMapper

| User input contains | → | `schedule.type` |
|---|---|---|
| "manual", "on-demand", "trigger only", "run when I say" | → | `manual` |
| "every N minutes", "every hour", "every day", "interval" | → | `interval` |
| "cron expression", "at 02:00 UTC", "weekdays at 9am" (anything that needs a cron spec) | → | `cron` |

After selecting `type`:

- `manual`: omit `interval_minutes` and `cron_expression`.
- `interval`: require `interval_minutes` (positive integer).
- `cron`: require `cron_expression` matching `^cron\(.+\)$` (AWS
  EventBridge / cron(…)) syntax. Runtime validates the inner spec.

## ReplicationMethodMapper

| User input contains | → | `replication.method` |
|---|---|---|
| "full refresh", "full reload", "reload everything", "snapshot" | → | `full_refresh` |
| "incremental", "delta", "changes since", "watermark" | → | `incremental` |

For `incremental`, the user must name the `cursor_field`. If they
can't, halt and ask for the column/parameter name they want to use as
the watermark.

`replication.method` must be in the source endpoint's declared support
set. For API endpoints, the connector document lists
`operations.read.replication.supported_methods`. For database endpoints
both methods are always supported.

## WriteModeMapper

| Destination kind | User input contains | → | `write.mode` |
|---|---|---|---|
| api | one of the endpoint's `operations.write` keys | → | that key (verbatim) |
| database | "insert", "append", "load" | → | `insert` |
| database | "upsert", "merge", "on-conflict update" | → | `upsert` (requires `conflict_keys`) |

For database `upsert`, ask the user (or infer from the destination
endpoint's `primary_keys`) which fields form the conflict resolution
key set. `conflict_keys` is `[[<field>, …], …]` — a non-empty array of
non-empty key sets.

## AuthTypeMapper

The orchestrator does **not** author the connector's `auth` block —
that's the connector-builder plugin's job. Here, `AuthTypeMapper`
selects which `connection-creator` template to use based on the
downloaded connector's `auth.type`:

| connector.auth.type | → | template |
|---|---|---|
| `api_key` | → | `examples/api-key.example.json` |
| `basic_auth` | → | `examples/basic-auth.example.json` |
| `oauth2_authorization_code` | → | `examples/oauth2-authorization-code.example.json` |
| `oauth2_client_credentials` | → | `examples/oauth2-client-credentials.example.json` |
| `jwt` | → | `examples/jwt.example.json` |
| `db` | → | `examples/db.example.json` |
| `credentials` | → | `examples/credentials.example.json` |
| `aws_iam` | → | `examples/aws-iam.example.json` |
| `none` | → | `examples/none.example.json` |

The connection-creator agent loads `connection-spec` and reads the
matching example. Any other `auth.type` value is a contract violation —
halt and report.
