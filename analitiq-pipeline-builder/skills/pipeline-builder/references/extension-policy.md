# `x-*` extension policy

Every authored entity supports custom metadata under keys matching:

```
^x-[a-z0-9]+(-[a-z0-9]+)*$
```

Examples: `x-team`, `x-cost-center`, `x-pii-class`, `x-source-ticket`.

## Where extensions are allowed

Top-level on every entity, and on every nested object that participates
in authoring. The published JSON Schemas declare
`patternProperties: {"^x-[a-z0-9]+(-[a-z0-9]+)*$": {}}` on the
appropriate definitions — meaning the server preserves the value but
does not interpret it.

## What the plugin does with extensions

Nothing automatic. Extensions are pass-through.

If the user asks the plugin to add an extension:

1. Validate the key against the regex above. Reject anything else.
2. Place the key/value at the requested object level.
3. Re-run the validator — the published schema explicitly allows the
   pattern, so it passes.

## What the plugin does NOT do

- Do **not** invent extension keys to communicate state between agents.
  Use `references/io-contracts.md` for that — those payloads live
  outside the authored document.
- Do **not** route around the validator by putting a non-conforming
  field under `x-foo`. Extensions are opaque metadata, not a back door.
