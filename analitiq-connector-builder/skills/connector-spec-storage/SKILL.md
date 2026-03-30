---
name: connector-spec-storage
disable-model-invocation: true
description: >
  Storage connector specification knowledge for S3, SFTP, and other file-based systems.
  Contains credentials auth configuration and storage connector examples. Load when creating
  or modifying a storage connector definition (connector.json).
---

# Storage Connector Specification

## Supporting Files

- [spec-form-based-storage.md](spec-form-based-storage.md) — storage form field definitions, credentials auth config
- `examples/` — complete connector.json examples (s3, sftp)

## Step 1: Read the Matching Example

Read from `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-storage/examples/`:

- `s3-connector.json` — Amazon S3 object storage
- `sftp-connector.json` — SFTP file transfer

## Step 2: Read the Detailed Specification

Read `${CLAUDE_PLUGIN_ROOT}/skills/connector-spec-storage/spec-form-based-storage.md` for the full storage connector schema including:
- Auth configuration (`auth.type: "credentials"`)
- Form field conventions (bucket, region, access keys for S3; host, port, username, password for SFTP)

## Step 3: Build the Connector JSON

### Quick Reference — Storage Connector Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `auth.type` | string | yes | Always `"credentials"` for storage connectors |
