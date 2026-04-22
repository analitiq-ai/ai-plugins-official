# `type_map` Format Specification

> Decision record for [issue #8](https://github.com/analitiq-ai/ai-plugins-official/issues/8).
> Consumed by [issue #7](https://github.com/analitiq-ai/ai-plugins-official/issues/7) (connector-builder adaptation) and the Arrow-adoption umbrella ticket.
> **Status:** decided. Do not re-litigate the format in #7.

## Purpose

Every connector's `connector.json` ships a `type_map`: an ordered list of rules
that map **native** types (Postgres `VARCHAR(255)`, MySQL `TINYINT(1)`, REST API
`number`, etc.) to **canonical** Arrow logical types (`Utf8`, `Boolean`,
`Decimal128(10, 2)`, `Timestamp(MICROSECOND, UTC)`, etc.).

This document specifies the **shape** of that field, the **match algorithm**,
**normalization** rules, **fallback** behavior, and the **capture-group
substitution** mechanism used for parameterized types.

Canonical types themselves — the Arrow logical type vocabulary — are defined in
a separate reference document per #7. This spec is orthogonal to the canonical
vocabulary: the same format works whether canonical is Arrow, a subset of
Arrow, or something else entirely.

## Format

`type_map` is a JSON **array of rule objects**. Order matters: rules are
evaluated top-to-bottom and the **first match wins**.

```json
"type_map": [
  { "match": "exact", "native": "JSONB",                              "canonical": "Utf8" },
  { "match": "exact", "native": "TINYINT(1)",                         "canonical": "Boolean" },
  { "match": "regex", "native": "^VARCHAR(\\(\\d+\\))?$",             "canonical": "Utf8" },
  { "match": "regex", "native": "^NUMERIC\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$", "canonical": "Decimal128(${p}, ${s})" },
  { "match": "regex", "native": "^TIMESTAMP(?:\\(\\d+\\))? WITH TIME ZONE$", "canonical": "Timestamp(MICROSECOND, UTC)" },
  { "match": "regex", "native": "^(?<base>.+)\\[\\]$",                "canonical": "List<${base}>" }
]
```

### Rule object

| Field       | Type   | Required | Notes |
|-------------|--------|----------|-------|
| `match`     | string | yes      | One of `"exact"`, `"regex"`. Closed set. |
| `native`    | string | yes      | Literal native type for `exact`; regex pattern for `regex`. |
| `canonical` | string | yes      | Target canonical type. May contain capture-group references (see [Substitution](#capture-group-substitution)). |

No other fields. `additionalProperties: false`.

### Why `exact` + `regex` only (no wildcard / prefix / base-name kinds)

Every additional match kind is a contract every engine implementation must
re-implement identically. `exact` + `regex` is universally available in every
language we target (Python `re`, Java `java.util.regex`, Go `regexp`, Rust
`regex`, JavaScript `RegExp`), and regex with the `^…$` anchor idiom
(`^TYPE(\(…\))?$`) handles every parameterized-type case cleanly. Adding
`prefix_paren` / `wildcard_glob` would buy ~5% syntactic brevity at a real cost
in cross-implementation drift.

### Why array-of-objects, not key-with-wildcards

Two reasons:

1. **Ordering must be explicit.** JSON object iteration order is not a
   reliable semantic carrier. Array order makes precedence visible in file and
   visible in diff.
2. **`first-match-wins` requires a `TINYINT(1) → Boolean` rule to appear
   *before* a generic `^TINYINT(\(\d+\))?$ → Int8` rule.** Arrays let authors
   express this ordering directly; object-keyed maps cannot.

## Match algorithm

```
match(native_input):
    normalized = normalize(native_input)   # see Normalization
    for rule in type_map:                  # top-to-bottom
        if rule.match == "exact":
            if normalized == normalize(rule.native):
                return substitute(rule.canonical, {})
        elif rule.match == "regex":
            m = regex.fullmatch(rule.native, normalized)
            if m:
                return substitute(rule.canonical, m.captures)
    raise UnmappedNativeType(native_input)   # see Fallback
```

- `fullmatch` (implicit `^…$` anchoring) is always applied — partial matches
  are never accepted, even if the author omits explicit anchors in the pattern.
  Engines must enforce this regardless of the regex literal.
- The **first** matching rule returns. Subsequent rules are not evaluated.
- Regex flavor: **ECMA-262 / RE2-compatible subset**. No backreferences, no
  lookaround. This is the intersection of every target language's default
  regex engine, so the same pattern behaves identically in all of them.

## Normalization

Applied to both `native_input` and `rule.native` (exact rules only) before
comparison. Never applied to the `canonical` field.

1. **Trim** leading and trailing whitespace.
2. **Collapse** runs of internal whitespace to a single space.
3. **Uppercase** the entire string.

So `timestamp  with  time  zone`, `TIMESTAMP WITH TIME ZONE`, and
` TimeStamp With Time Zone ` all normalize to `TIMESTAMP WITH TIME ZONE`.

**Regex patterns are NOT normalized** — they are used as-is against the
normalized input. Authors write patterns in the normalized (uppercase,
single-space) form.

### Aliases are separate rules, not a normalization concern

Postgres reports `TIMESTAMPTZ` and `TIMESTAMP WITH TIME ZONE` as distinct
literals. Both should map to the same canonical. Authors write **two rules**:

```json
{ "match": "exact", "native": "TIMESTAMPTZ",              "canonical": "Timestamp(MICROSECOND, UTC)" },
{ "match": "exact", "native": "TIMESTAMP WITH TIME ZONE", "canonical": "Timestamp(MICROSECOND, UTC)" }
```

A dedicated `aliases` mechanism was rejected: it would require per-connector
alias tables (more config, not less) and it hides the `native → canonical`
relationship behind an indirection layer.

## Capture-group substitution

Parameterized native types (`NUMERIC(10, 2)`, `VARCHAR(255)`,
`TIMESTAMP(6) WITH TIME ZONE`) map to parameterized canonical types
(`Decimal128(10, 2)`, `Utf8`, `Timestamp(MICROSECOND, UTC)`). The `canonical`
field may reference named capture groups from the `native` regex using
`${name}` syntax.

### Rules

1. **Named groups only.** `(?<name>…)` in the pattern, `${name}` in the
   substitution. Positional groups (`$1`, `$2`) are **not** supported —
   named groups are self-documenting and resist off-by-one errors when
   patterns evolve.
2. **`exact` rules cannot use substitution** — there are no capture groups
   to reference. A canonical with `${…}` in an `exact` rule is a validation
   error.
3. **Every `${name}` in `canonical` must correspond to a named group in the
   `native` pattern.** Dangling references are a validation error.
4. **Substitution is literal** — the captured text is spliced in without
   further processing. No arithmetic, no casting, no defaults. If the
   canonical needs a transformation the native type doesn't provide, write
   a more specific rule above it.

### Examples

```json
{ "match": "regex",
  "native":    "^NUMERIC\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
  "canonical": "Decimal128(${p}, ${s})" }
```

Input `NUMERIC(18, 4)` → captures `p=18`, `s=4` → emits `Decimal128(18, 4)`.

```json
{ "match": "regex",
  "native":    "^(?<base>[A-Z0-9_]+)\\[\\]$",
  "canonical": "List<${base}>" }
```

Input `INTEGER[]` → captures `base=INTEGER` → emits `List<INTEGER>`.

**Caveat on the array example:** the base type inside `List<…>` is itself a
native type name, not yet canonicalized. A second lookup is needed to resolve
it. Engines may perform that recursively; authors should prefer emitting
already-canonical content where feasible (e.g., explicit rules for
`INTEGER[]` → `List<Int32>` before the generic fallback).

## Fallback

If no rule in `type_map` matches a given native type, the matcher **raises an
error**. It does not default to any canonical type.

Rationale:

- A silent default (e.g., to `Utf8`) would hide new native types the connector
  author has not explicitly handled. Schema drift in production is worse than
  a loud failure at authoring or ingest time.
- `HSTORE`, `CITEXT`, `MONEY`, `GEOMETRY(Point, 4326)` — every one of these is
  a judgment call. Silent coercion to string corrupts data.
- The author-time LLM gap-fill workflow (per #7) exists precisely to reduce the
  burden of enumerating rare types. It is **not** a runtime fallback: the LLM
  proposes rules, a human commits them, and then the map covers those natives.
  No LLM is invoked at pipeline runtime.

## JSON Schema fragment

For inclusion in the connector-level JSON Schema once the canonical types
reference is published in #7:

```json
{
  "$id": "https://analitiq.dev/schemas/type-map.json",
  "title": "type_map",
  "description": "Ordered list of native → canonical type mapping rules. First match wins.",
  "type": "array",
  "minItems": 1,
  "items": {
    "type": "object",
    "required": ["match", "native", "canonical"],
    "additionalProperties": false,
    "properties": {
      "match":     { "enum": ["exact", "regex"] },
      "native":    { "type": "string", "minLength": 1 },
      "canonical": { "type": "string", "minLength": 1 }
    },
    "allOf": [
      {
        "if":   { "properties": { "match": { "const": "exact" } } },
        "then": {
          "properties": {
            "canonical": {
              "not": { "pattern": "\\$\\{[^}]+\\}" },
              "description": "exact rules cannot use ${name} substitution"
            }
          }
        }
      }
    ]
  }
}
```

The `canonical` string is not schema-validated against the Arrow logical type
vocabulary here — that validation is the job of the canonical-types reference
published by #7. This schema only validates the **shape** of `type_map`.

An additional semantic check — every `${name}` in `canonical` has a matching
named group in `native` — is out of scope for JSON Schema and performed by the
validator API / authoring skill in #7.

## Worked examples

### Postgres

```json
"type_map": [
  { "match": "exact", "native": "BOOLEAN",                  "canonical": "Boolean" },
  { "match": "exact", "native": "SMALLINT",                 "canonical": "Int16" },
  { "match": "exact", "native": "INTEGER",                  "canonical": "Int32" },
  { "match": "exact", "native": "BIGINT",                   "canonical": "Int64" },
  { "match": "exact", "native": "REAL",                     "canonical": "Float32" },
  { "match": "exact", "native": "DOUBLE PRECISION",         "canonical": "Float64" },
  { "match": "exact", "native": "TEXT",                     "canonical": "Utf8" },
  { "match": "exact", "native": "UUID",                     "canonical": "Utf8" },
  { "match": "exact", "native": "JSON",                     "canonical": "Utf8" },
  { "match": "exact", "native": "JSONB",                    "canonical": "Utf8" },
  { "match": "exact", "native": "DATE",                     "canonical": "Date32" },
  { "match": "exact", "native": "TIMESTAMPTZ",              "canonical": "Timestamp(MICROSECOND, UTC)" },
  { "match": "exact", "native": "TIMESTAMP WITHOUT TIME ZONE", "canonical": "Timestamp(MICROSECOND, null)" },
  { "match": "regex", "native": "^VARCHAR(\\(\\d+\\))?$",   "canonical": "Utf8" },
  { "match": "regex", "native": "^CHARACTER VARYING(\\(\\d+\\))?$", "canonical": "Utf8" },
  { "match": "regex", "native": "^CHAR(\\(\\d+\\))?$",      "canonical": "Utf8" },
  { "match": "regex", "native": "^NUMERIC\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$", "canonical": "Decimal128(${p}, ${s})" },
  { "match": "regex", "native": "^NUMERIC\\((?<p>\\d+)\\)$", "canonical": "Decimal128(${p}, 0)" },
  { "match": "exact", "native": "NUMERIC",                  "canonical": "Decimal128(38, 9)" },
  { "match": "regex", "native": "^TIMESTAMP(?:\\(\\d+\\))? WITH TIME ZONE$", "canonical": "Timestamp(MICROSECOND, UTC)" },
  { "match": "regex", "native": "^TIMESTAMP(?:\\(\\d+\\))?(?: WITHOUT TIME ZONE)?$", "canonical": "Timestamp(MICROSECOND, null)" }
]
```

Match walk-throughs (input → normalized → matched rule → canonical):

| Input                          | Normalized                      | Matched rule              | Canonical                            |
|--------------------------------|---------------------------------|---------------------------|--------------------------------------|
| `jsonb`                        | `JSONB`                         | exact `JSONB`             | `Utf8`                               |
| `varchar(255)`                 | `VARCHAR(255)`                  | regex `^VARCHAR(\(\d+\))?$` | `Utf8`                             |
| `numeric(18,4)`                | `NUMERIC(18,4)`                 | regex `^NUMERIC\((?<p>\d+),\s*(?<s>\d+)\)$` | `Decimal128(18, 4)` |
| `timestamp(6) with time zone`  | `TIMESTAMP(6) WITH TIME ZONE`   | regex `^TIMESTAMP(?:\(\d+\))? WITH TIME ZONE$` | `Timestamp(MICROSECOND, UTC)` |
| `hstore`                       | `HSTORE`                        | _no match_                | error (author must add a rule)       |

### MySQL

```json
"type_map": [
  { "match": "exact", "native": "TINYINT(1)",               "canonical": "Boolean" },
  { "match": "regex", "native": "^TINYINT(\\(\\d+\\))?(?:\\s+UNSIGNED)?$", "canonical": "Int8" },
  { "match": "regex", "native": "^SMALLINT(\\(\\d+\\))?(?:\\s+UNSIGNED)?$", "canonical": "Int16" },
  { "match": "regex", "native": "^MEDIUMINT(\\(\\d+\\))?(?:\\s+UNSIGNED)?$", "canonical": "Int32" },
  { "match": "regex", "native": "^INT(\\(\\d+\\))?(?:\\s+UNSIGNED)?$", "canonical": "Int32" },
  { "match": "regex", "native": "^BIGINT(\\(\\d+\\))?(?:\\s+UNSIGNED)?$", "canonical": "Int64" },
  { "match": "exact", "native": "FLOAT",                    "canonical": "Float32" },
  { "match": "exact", "native": "DOUBLE",                   "canonical": "Float64" },
  { "match": "regex", "native": "^DECIMAL\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$", "canonical": "Decimal128(${p}, ${s})" },
  { "match": "regex", "native": "^VARCHAR\\(\\d+\\)$",      "canonical": "Utf8" },
  { "match": "regex", "native": "^CHAR\\(\\d+\\)$",         "canonical": "Utf8" },
  { "match": "exact", "native": "TEXT",                     "canonical": "Utf8" },
  { "match": "exact", "native": "LONGTEXT",                 "canonical": "Utf8" },
  { "match": "regex", "native": "^ENUM\\(.+\\)$",           "canonical": "Utf8" },
  { "match": "exact", "native": "DATE",                     "canonical": "Date32" },
  { "match": "regex", "native": "^DATETIME(\\(\\d+\\))?$",  "canonical": "Timestamp(MICROSECOND, null)" },
  { "match": "regex", "native": "^TIMESTAMP(\\(\\d+\\))?$", "canonical": "Timestamp(MICROSECOND, UTC)" },
  { "match": "exact", "native": "JSON",                     "canonical": "Utf8" }
]
```

**Precedence note:** the `TINYINT(1)` rule is intentionally placed *above* the
generic `TINYINT(…)` rule. If the order were reversed, every `TINYINT(1)`
column would match the generic rule first and canonicalize to `Int8`, silently
discarding MySQL's convention that `TINYINT(1)` represents a boolean. The
`first-match-wins` rule makes specificity-before-generality the author's
responsibility, visible in file order.

## Open questions deferred to #7 / engine repo

- The authoring-skill workflow for programmatic matching + LLM gap-fill is
  part of #7's `type-mapping-spec` skill, not this spec.
- The engine's implementation of the matcher (in whatever languages the engine
  uses) is tracked in the engine repo. This spec is the contract it consumes.
- Destination-side use of `type_map` (reverse lookup: canonical → preferred
  native) is covered by the Arrow-adoption umbrella ticket, not this spec.