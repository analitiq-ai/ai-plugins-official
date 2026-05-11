# Identity and versioning

Pipelines and streams reference each other and their connections by
**versioned UUIDs**. The plugin mints stable placeholder UUIDs locally
because it does not call any registration API. The user / registry
replaces them at submission time.

## Versioned ID format

```
<uuid>_v<positive integer>
```

Pattern (anchored):
`^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}_v[1-9][0-9]*$`

The UUID part is canonical-form lowercase hex (any v1–v5).
The `_v<n>` suffix is a positive integer starting at `_v1`.

A **base UUID** is the same UUID without the `_v<n>` suffix. Stream
documents declare `pipeline_id` as a base UUID, never versioned —
because the stream points at the parent's identity, not at a pinned
version of the parent.

## Placeholder minting (deterministic UUID v5)

The orchestrator mints placeholders so that re-running against the same
inputs produces the same IDs. This makes the output diff-friendly and
keeps cross-document references stable across re-runs.

```python
import uuid
def placeholder_connection_id(connection_alias: str) -> str:
    base = uuid.uuid5(uuid.NAMESPACE_URL, f"analitiq:connection:{connection_alias}")
    return f"{base}_v1"

def placeholder_pipeline_id(pipeline_alias: str) -> str:
    base = uuid.uuid5(uuid.NAMESPACE_URL, f"analitiq:pipeline:{pipeline_alias}")
    return f"{base}_v1"

def placeholder_stream_id(pipeline_alias: str, stream_alias: str) -> str:
    base = uuid.uuid5(uuid.NAMESPACE_URL, f"analitiq:stream:{pipeline_alias}/{stream_alias}")
    return f"{base}_v1"
```

`stream.pipeline_id` is the **base** UUID — i.e. strip the `_v1` from
`placeholder_pipeline_id(pipeline_alias)`.

## Server-managed `version` field

Pipelines and streams have a server-managed integer `version` field.
**The plugin does not author it.** The registry sets `version: 1` on
insert and increments on certain updates per the published lifecycle
contract. See `reserved-fields.md`.

This is different from connectors, which use semver and a drift
classifier to bump the field. Pipelines and streams use a counter, and
the registry owns it.

## Why placeholders, not API calls

This plugin authors locally and never calls the registration API.
Rationale:

- No auth handling burden inside the plugin.
- No network dependency for the build path.
- Diff-friendly output (deterministic IDs).
- Clean separation: the plugin produces structurally-correct JSON; the
  registry owns identity.

The user replaces the placeholders with real IDs at submission time
(typically by uploading the directory to the registry's API or by
running a separate registration command).
