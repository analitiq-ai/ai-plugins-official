# DSN URL templates + bindings

The full authoring contract for `transports.<name>.dsn` when
`dsn.kind == "url_template"`.

## Shape

```json
{
  "dsn": {
    "kind": "url_template",
    "template": "postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}",
    "bindings": {
      "username": { "value": { "ref": "connection.parameters.username" }, "encoding": "url_userinfo" },
      "password": { "value": { "ref": "secrets.password" }, "encoding": "url_userinfo" },
      "host":     { "value": { "ref": "connection.parameters.host" }, "encoding": "host" },
      "port":     { "value": { "ref": "connection.parameters.port" }, "encoding": "raw" },
      "database": { "value": { "ref": "connection.parameters.database" }, "encoding": "url_path_segment" }
    }
  }
}
```

## Rules

- `template` is a connector-authored string with `{placeholder}` markers.
  No direct `${...}` context references — those go inside binding `value`
  expressions.
- Every placeholder in the template must have a matching binding key.
- Every binding key should appear in the template (the `dsn-binding`
  validator emits a warning when unused; an extra binding is allowed if
  the transport documents another use for it).
- Each binding declares:
  - `value` — a value expression (`ref` or `template` or `function`).
  - `encoding` — one of the closed enum values listed below.

## Encoding values (closed enum)

| Encoding | Use |
|---|---|
| `raw` | No encoding. Numeric or already-safe values (port, integers). |
| `host` | Hostname encoding rules (IPv6 brackets, IDN punycode). |
| `url_userinfo` | RFC 3986 userinfo encoding (passwords, usernames). |
| `url_path_segment` | RFC 3986 path-segment encoding (database names that may contain special chars). |
| `url_query_key` | RFC 3986 query-key encoding. |
| `url_query_value` | RFC 3986 query-value encoding (query parameter values such as warehouse, schema). |

## Authoring checklist

1. Pick the canonical DSN form for the driver (look at SQLAlchemy /
   driver documentation).
2. Write the template with one `{placeholder}` per logical field.
3. For each placeholder, declare the binding's `value` and `encoding`.
4. Use `secrets.password` for the password — never `connection.parameters.password`.
5. Never pre-encode any value. The runtime applies the declared encoding.

## Driver examples

| Driver | Template |
|---|---|
| `postgresql+asyncpg` | `postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}` |
| `mysql+asyncmy` | `mysql+asyncmy://{username}:{password}@{host}:{port}/{database}` |
| `snowflake` | `snowflake://{username}:{password}@{account}/{database}/{schema}?warehouse={warehouse}&role={role}` |
| `mongodb` | `mongodb://{username}:{password}@{host}:{port}/{database}?authSource=admin` |

`mongodb` lives in a SQLAlchemy-shaped transport entry only when there's
a SQLAlchemy adapter; for the canonical driver, prefer a transport
declaration that uses MongoDB's native connection string format.
