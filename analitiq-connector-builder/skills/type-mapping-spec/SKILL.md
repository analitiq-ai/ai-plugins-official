---
name: type-mapping-spec
disable-model-invocation: true
description: >
  Authoring knowledge for `type-map.json` and (for SSL-capable databases) `ssl-mode-map.json`,
  the standalone files that sit alongside `connector.json` in `definition/`. Covers the
  canonical type vocabulary (Apache Arrow logical types) and the three authoring methodologies:
  `exact` rules, `regex` rules with `${name}` substitution, and agent judgment for semantic
  cases. Load when creating or modifying a connector definition.
---

# Type Mapping Specification

## Supporting files

- `${CLAUDE_PLUGIN_ROOT}/schemas/canonical-types.json` — JSON Schema defining the canonical Arrow logical type vocabulary. `$id: https://analitiq.dev/schemas/canonical-types.json`. `$ref` from downstream schemas; never restate the vocabulary in prose.
- `${CLAUDE_PLUGIN_ROOT}/docs/type-map-format.md` — format spec for `type-map.json`: match algorithm, normalization, capture-group substitution, JSON Schema fragment, Postgres + MySQL worked examples.

Read both before authoring.

## Files this skill produces

Both sit in `{slug}/definition/` alongside `connector.json`, `manifest.json`, and `endpoints/`.

| File | Required | Which connectors |
|------|----------|------------------|
| `type-map.json` | yes | every connector (API, DB, storage) |
| `ssl-mode-map.json` | no | only SSL-capable databases; omit entirely otherwise |

Neither is a field inside `connector.json`. Each is a standalone file with its own `$schema` / `$id` and validator.

## `type-map.json`

Shape per `${CLAUDE_PLUGIN_ROOT}/docs/type-map-format.md`: a top-level JSON array of `{match, native, canonical}` rules. `$schema: "https://analitiq.dev/schemas/type-map.json"`.

### Canonical vocabulary (from `schemas/canonical-types.json`)

- **Unparameterized:** `Null`, `Boolean`, `Int8..Int64`, `UInt8..UInt64`, `Float16/32/64`, `Binary`, `LargeBinary`, `Utf8`, `LargeUtf8`, `Date32`, `Date64`.
- **Parameterized primitives:** `FixedSizeBinary(n)`, `Time32(unit)`, `Time64(unit)`, `Timestamp(unit, tz)`, `Duration(unit)`, `Interval(unit)`, `Decimal128(p, s)`, `Decimal256(p, s)`.
- **Nested:** `List<T>`, `LargeList<T>`, `FixedSizeList<T>[n]`, `Struct<f:T>`, `Map<K, V>`, `SparseUnion<...>`, `DenseUnion<...>`, `Dictionary<K, V>`, `RunEndEncoded<K, V>`.

Write canonical strings in exactly this form — the schema validates them.

### Three authoring methodologies

Pick exactly one methodology per distinct native type. All three produce rules of the same shape (`{match, native, canonical}`); they differ in *how* the rule is authored.

**Methodology 1 — `exact`** for unparameterized standard natives with a fixed 1:1 mapping:

```json
{ "match": "exact", "native": "BOOLEAN", "canonical": "Boolean" }
{ "match": "exact", "native": "TEXT",    "canonical": "Utf8" }
{ "match": "exact", "native": "JSONB",   "canonical": "Utf8" }
```

**Methodology 2 — `regex` with named captures + `${name}` substitution** for parameterized families where the canonical is a mechanical transform:

```json
{ "match": "regex",
  "native":    "^NUMERIC\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
  "canonical": "Decimal128(${p}, ${s})" }

{ "match": "regex",
  "native":    "^VARCHAR(\\(\\d+\\))?$",
  "canonical": "Utf8" }

{ "match": "regex",
  "native":    "^TIMESTAMP(?:\\(\\d+\\))? WITH TIME ZONE$",
  "canonical": "Timestamp(MICROSECOND, UTC)" }
```

Named groups only; no positional `$1`. `exact` rules cannot substitute.

**Pairing invariant:** every `${name}` reference in `canonical` must have a matching named capture group `(?<name>…)` in `native`. The JSON Schema validates file shape only — this invariant is enforced by the validator API and must be checked by the authoring agent before committing. A regex with positional captures cannot be paired with `${…}` substitution.

Common mistake:

```json
// WRONG — positional captures can't be referenced via ${name}.
// Passes JSON Schema, fails at runtime with literal "${p}" in the canonical.
{ "match": "regex",
  "native":    "^NUMERIC\\((\\d+),\\s*(\\d+)\\)$",
  "canonical": "Decimal128(${p}, ${s})" }

// RIGHT — named captures pair with ${name} references.
{ "match": "regex",
  "native":    "^NUMERIC\\((?<p>\\d+),\\s*(?<s>\\d+)\\)$",
  "canonical": "Decimal128(${p}, ${s})" }
```

**Methodology 3 — Agent judgment (author-time only)** for native types that neither Methodology 1 nor Methodology 2 can handle mechanically. The authoring agent proposes **`exact` rules** based on its own understanding of the source system's conventions, engine policy, and domain knowledge; a human reviews and commits. The output rules look identical to Methodology 1's; the difference is how the agent arrived at them. Triggers:

- **Semantically ambiguous:** `HSTORE` (→ `Utf8` vs `Map<Utf8,Utf8>`), `MONEY`, `JSON`/`JSONB` (blob vs inferred struct), `CIDR`/`INET`, `BYTEA`/`BLOB` (`Binary` vs `LargeBinary`).
- **Convention-dependent:** MySQL `TINYINT(1)` → `Boolean`; Oracle `NUMBER` without precision; Oracle `VARCHAR2` preferred over `VARCHAR`; SQL Server `BIT` → `Boolean`.
- **Spatial / domain-specific:** PostGIS `GEOMETRY(Point, 4326)`, `GEOGRAPHY(...)`, `XML`, pgvector `vector(N)` → `FixedSizeList<Float32>[N]`.
- **Enum value domain:** `ENUM('a','b','c')` → `Utf8`; value list goes into connector metadata, not `type-map.json`.
- **Vendor extensions:** `citext`, `ltree`, `cube`, range types, etc.
- **Precision/unit defaults** for under-specified natives: bare `TIMESTAMP` without precision, `FLOAT` variants across engines.

### Authoring order

1. `exact` rules for every unparameterized standard native from the source's documented type list.
2. `regex` rules for each parameterized family, with named captures.
3. **Specific-before-generic.** First-match-wins: `TINYINT(1) → Boolean` must precede generic `^TINYINT(\(\d+\))? → Int8`.
4. Agent judgment for leftovers (Methodology 3). Human confirms.
5. Do not invent rules for natives that aren't in the source's documented type list.
6. **Verify coverage.** Enumerate the full native type list from the source's official documentation. For each native, confirm it matches an authored rule (from Methodology 1, 2, or 3). Any native without a matching rule must be either (a) handled by agent judgment in step 4, or (b) explicitly reported to the orchestrator as an intentional omission with a reason. Do not finish authoring until every documented native is accounted for.

### Storage connectors — narrower scope

Storage connectors (S3, SFTP, blob stores) do **not** have a connector-level native type vocabulary. File-data types come from the file format being read at runtime (CSV, Parquet, JSONL, …) and are handled by the engine's file-format readers, **not** by `type-map.json`.

For storage connectors, `type-map.json` covers **connector-level metadata types only** — the object listing fields the connector itself returns (e.g. object key → `Utf8`, size → `Int64`, last-modified → `Timestamp(MICROSECOND, UTC)`). Do not attempt to enumerate CSV / Parquet / JSONL column types here; they are out of scope for this file.

## `ssl-mode-map.json` (SSL-capable DBs only)

Standalone file with `$schema: "https://analitiq.dev/schemas/ssl-mode-map.json"`. Maps native driver SSL mode values to `canonical_ssl_mode` (`none | require | verify-ca | verify-full | prefer`) defined in `schemas/canonical-types.json`. Enum values mirror Postgres `sslmode` / MySQL `--ssl-mode` vocabulary, so common drivers produce near-1:1 mappings.

```json
{
  "$schema": "https://analitiq.dev/schemas/ssl-mode-map.json",
  "disable":     "none",
  "require":     "require",
  "verify-ca":   "verify-ca",
  "verify-full": "verify-full",
  "prefer":      "prefer"
}
```

**Do NOT collapse `verify-ca` and `verify-full` onto a single canonical value.** The chain-only vs chain+hostname distinction is security-relevant — a user who deliberately configured hostname-off (internal CA, proxy, relaxed environment) must get `verify-ca` at runtime, not `verify-full`.

Native values come from the source driver's official docs. Do not create this file on API, storage, or DB connectors without TLS support.

If the research input does not clearly state whether a DB driver supports TLS, or how it enumerates TLS modes (common for drivers that take TLS as a URL param or boolean rather than a named enum), **do not silently omit**. Report the ambiguity to the orchestrator and let a human decide — silent omission on a TLS-capable driver is a correctness bug.

## What NOT to canonicalize

- **Endpoint JSON Schema types** (`string`, `integer`, `number`, `boolean`, `object`, `array`) stay in endpoint schemas. The `type-map.json` bridges JSON Schema → Arrow at engine ingest; endpoint schemas are not rewritten.
- **Field/column names.** `type-map.json` maps types, not columns.
- **Nullability.** Not part of canonical strings; Arrow tracks it at field/array level.
- **Precision overrides.** Do not hand-edit committed canonical strings. Schema evolution goes through the same `type-map.json` lookup.