# Schema hosts: dev (.work) and prod (.ai)

Two hosts serve identical schema content during the migration window.
The split is intentional.

| Concern | Host | Why |
|---|---|---|
| Document's `$schema` declaration | `https://schemas.analitiq.ai/` | The schema's own `$schema` `const` locks this. Authored docs declare the production URL so they don't need to change when prod cuts over. |
| Validator's schema fetch | `https://schemas.analitiq.work/` | Dev host. The script in `scripts/validate_pipeline.py` defaults to this. |

When production cuts over, only the validator's fetch host flips to
`.ai`. Authored documents (and existing on-disk artifacts) already
point at the production host, so they don't change.

## How to verify locally

```bash
python scripts/validate_pipeline.py \
  --entity pipeline \
  --document path/to/pipeline.json
# default schema-url:
#   https://schemas.analitiq.work/pipeline/latest.json
```

Override the fetch host if needed:

```bash
python scripts/validate_pipeline.py \
  --entity pipeline \
  --document path/to/pipeline.json \
  --schema-url https://schemas.analitiq.ai/pipeline/latest.json
```

## Cache notes

The validator caches fetched schemas under
`~/.cache/analitiq/schemas/<sha256-prefix>.json`. The cache key is the
**URL**, so dev and prod URLs cache independently. Use `--no-cache` to
force a fresh fetch — useful when you suspect schema drift.
