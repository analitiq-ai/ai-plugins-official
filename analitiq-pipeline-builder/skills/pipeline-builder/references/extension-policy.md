# Extension policy

The published Analitiq schemas are **closed**:
`additionalProperties: false` is in effect on every authored entity.
Unknown fields — including any `x-*` keys — are rejected at validation
time.

The plugin does not author extension keys. If the user asks the plugin
to attach extra metadata to a document, decline and surface a clear
message: the published contract does not accept unknown fields, and the
plugin will not route around the validator by smuggling data into a
known field.

Cross-agent state (the orchestrator's payloads between phases) is **not**
part of the authored document — that lives in
`references/io-contracts.md`. Use those payloads for any inter-agent
communication; never use the authored JSON as a side-channel.
