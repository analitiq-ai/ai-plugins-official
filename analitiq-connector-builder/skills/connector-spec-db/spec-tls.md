# TLS declarations

How database connectors declare TLS intent without embedding driver-
specific objects.

## Shape

```json
{
  "transports": {
    "database": {
      "tls": {
        "mode": { "ref": "connection.parameters.ssl_mode" },
        "ca_certificate": { "ref": "secrets.ssl_ca_certificate" }
      }
    }
  }
}
```

## Rules

- `tls.mode` is a value expression that resolves to one of the canonical
  enum values: `none`, `require`, `verify-ca`, `verify-full`, `prefer`.
  In practice it should `ref` the canonical input
  `connection.parameters.ssl_mode`.
- `tls.ca_certificate` is a value expression that resolves to a
  PEM-encoded CA bundle. It should `ref` the canonical secret
  `secrets.ssl_ca_certificate`.
- If the `ssl_mode` enum allows `verify-ca` or `verify-full`, the
  connection contract must declare `ssl_ca_certificate` as an input.
  The `tls-consistency` validator enforces this.
- Connector authors must NOT embed driver-specific TLS objects, file
  paths, or executable code in connector JSON. The runtime materializer
  converts the generic declaration into driver-specific arguments.

## Canonical SSL mode enum

The canonical `ssl_mode` values across drivers are:

| Mode | Meaning |
|---|---|
| `none` | Plain (no TLS). |
| `require` | TLS without certificate validation. |
| `verify-ca` | TLS with CA validation, no hostname check. |
| `verify-full` | TLS with CA + hostname validation. |
| `prefer` | TLS if available, fall back to plain. |

If a driver uses different mode names (e.g. `disable`, `allow`,
`require`), declare a `ssl-mode-map.json` alongside `connector.json` to
translate driver-native values to the canonical enum. The runtime uses
the map at materialization time.

## Authoring checklist

1. Always declare `ssl_mode` as a connection input with an explicit
   `enum`.
2. Always declare `ssl_ca_certificate` as a secret input when
   `verify-ca`/`verify-full` are in the enum.
3. Reference both via `ref` inside the transport's `tls` block.
4. Do not duplicate driver-specific SSL options elsewhere — if the
   driver needs additional connection arguments derived from `ssl_mode`,
   the engine handles that.
