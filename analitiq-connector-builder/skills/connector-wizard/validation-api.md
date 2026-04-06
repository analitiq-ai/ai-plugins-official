# Validation API Reference

The Analitiq validation API validates connector and endpoint JSON against the authoritative Pydantic
models to ensure 100% compliance. Without validation, agents may produce JSON with subtle errors.

## Collecting the API Key

1. Check if the environment variable `ANALITIQ_API_KEY` is set (run `echo $ANALITIQ_API_KEY`).
2. If not set, ask the user: *"Do you have an Analitiq API key? You can get one for free at
   analitiq-app.com. This lets us validate the connector against the official schema to ensure
   it's 100% compliant. It's optional but recommended."*
3. If the user provides a key, use it for validation. If they decline, skip validation and proceed
   without it — but warn that the output may contain errors.

## Validation API

**Base URL:** `https://rest.analitiq-dev.com/v1`
**Auth:** `x-api-key` header with the API key

**Validate a connector:**
```bash
curl -s -X POST "https://rest.analitiq-dev.com/v1/validate/connector" \
  -H "x-api-key: $ANALITIQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d @{slug}/definition/connector.json
```

**Validate an endpoint:**
```bash
curl -s -X POST "https://rest.analitiq-dev.com/v1/validate/endpoint" \
  -H "x-api-key: $ANALITIQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d @{slug}/definition/endpoints/{endpoint_name}.json
```

**Responses:**
- `200 {"valid": true}` — JSON is compliant
- `422` — validation errors (Pydantic format):
  ```json
  {"valid": false, "errors": [{"type": "missing", "loc": ["field_name"], "msg": "Field required"}]}
  ```
  Each error has `type` (error kind), `loc` (field path as array), and `msg` (human-readable message).
  Use `loc` to find the field and `msg` to understand what to fix.
- `400 {"valid": false, "message": "..."}` — bad request (malformed JSON, unknown schema type)

## Validation Workflow

After Phase 2 (connector) and Phase 3 (endpoints, if API):

1. **Validate the connector**: `POST /validate/connector` with `connector.json` body.
   - If invalid: read the errors, fix the JSON, and re-validate until it passes.
2. **Validate each endpoint** (API connectors only): `POST /validate/endpoint` with each endpoint JSON body.
   - If invalid: read the errors, fix the JSON, and re-validate until it passes.
3. **If ALL validations pass**: the connector is compliant. Record the validation status for
   use in Phase 6 (community contribution). The handling depends on context:
   - **New connector (local, not yet in the registry)**: Record `validation_status: "validated"`
     in the connector-wizard context. The `registry-contributor` agent includes this status in the
     submission issue. Do NOT run `gh repo edit` — the registry repo does not exist yet.
   - **Existing connector (already in `analitiq-dip-registry`)**: Add the `validated` topic:
     ```bash
     gh repo edit analitiq-dip-registry/{slug} --add-topic validated
     ```
4. **If validation was skipped** (no API key): record `validation_status: "not validated"`.
   Do NOT add the `validated` topic.

## Updating Existing Connectors

When updating an existing connector repo (adding endpoints, modifying connector.json):
- Re-validate ALL connector and endpoint files, not just the changed ones.
- If the connector is already in the `analitiq-dip-registry` org:
  - If all pass, ensure the `validated` topic is present.
  - If any fail, remove the `validated` topic if it was previously set:
    ```bash
    gh repo edit analitiq-dip-registry/{slug} --remove-topic validated
    ```
- If the connector is local only, update the `validation_status` in the connector-wizard context.