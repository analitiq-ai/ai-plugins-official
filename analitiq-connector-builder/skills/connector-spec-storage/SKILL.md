---
name: connector-spec-storage
description: Stub for storage-style connector kinds (file, s3, stdout). Schema accepts these kinds but engine support is not yet shipped, so this skill is intentionally minimal. Loaded only by storage-connector-creator (also a stub) when the orchestrator dispatches a storage kind.
disable-model-invocation: true
---

# connector-spec-storage (stub)

This skill is a placeholder. The published connector schema accepts
`kind ∈ {file, s3, stdout}`, but the Analitiq engine does not execute
these kinds yet. Until engine support lands:

- The orchestrator should route `kind = file | s3 | stdout` to the
  `storage-connector-creator` agent.
- `storage-connector-creator` declines to author and returns a
  structured note explaining why.
- This skill exists so future expansion (auth flows, transports,
  encoding rules for storage) has a place to live without restructuring
  the skill tree.

When engine support arrives, expand this skill with:

- `spec-file-transport.md` — local filesystem path templates and access
  modes.
- `spec-s3-transport.md` — S3 endpoint, region, prefix templates;
  `S3CredentialsBlock` shape; assume-role flows.
- `spec-stdout-transport.md` — debug sink configuration.
- `examples/` — one validated example per kind.
