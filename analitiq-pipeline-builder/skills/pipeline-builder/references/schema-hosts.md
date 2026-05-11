# Schema host

All Analitiq schemas are served from a single host: `https://schemas.analitiq.ai/`.

| Concern | Host |
|---|---|
| Document's `$schema` declaration | `https://schemas.analitiq.ai/` (locked by a `const` inside the schema) |
| Validator's schema fetch | `https://schemas.analitiq.ai/` (default in `scripts/validate_pipeline.py`) |

## How to verify locally

```bash
python scripts/validate_pipeline.py \
  --entity pipeline \
  --document path/to/pipeline.json
# default schema-url:
#   https://schemas.analitiq.ai/pipeline/latest.json
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
**URL**. Use `--no-cache` to force a fresh fetch — useful when you
suspect schema drift.
