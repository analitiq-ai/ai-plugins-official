Technical Instructions for Mapping Review / Creation Agent

1. Understand the Mapping Architecture

Every stream mapping has three coupled sections that must stay in sync:

┌────────────────────────┬──────────────────────────────────────────────────────────────────────────────┐
│        Section         │                                   Purpose                                    │
├────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
│ assignments            │ The actual field-level mapping rules (expr or const → target)                │
├────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
│ source_to_generic      │ Declares which source fields are used and their generic types                │
├────────────────────────┼──────────────────────────────────────────────────────────────────────────────┤
│ generic_to_destination │ Declares destination fields, their types, and nullability per connection ref │
└────────────────────────┴──────────────────────────────────────────────────────────────────────────────┘

When you add, remove, or change an assignment, you must update all three sections.

2. Valid Type Enum

The system uses a strict Pydantic enum for types. The only valid values are:

string | integer | decimal | boolean | date | datetime | object | array

Common mistakes:
- number / float / double → use "decimal"
- int → use "integer"
- bool → use "boolean"
- timestamp → use "datetime"
- dict / json → use "object"
- list → use "array"

3. Understand Source vs Destination Semantics

Before writing any mapping, answer these questions:

For the source:
- What does the raw API/DB response look like? What is each field's actual runtime type and structure?
- Are fields flat or nested? (e.g., originator is an object containing name.fullName, not a string)
- What are the possible values? (e.g., Wise status is a string like "funds_converted")

For the destination:
- What HTTP method / DB operation is being used? (POST = create, PUT = update)
- Which fields are required vs optional for that operation?
- Which fields are response-only and must NOT be sent? (e.g., id, objectName on a POST/create endpoint)
- What types does the destination actually expect? (e.g., SevDesk status is an integer enum 100|200|300|400, amount is a float, checkAccount is a JSON object)
- Are there enum constraints? What values are valid?

Critical rule: sending id in a POST body often makes APIs interpret the request as an update, causing 404 errors when the ID doesn't exist on the destination side.

4. Assignment Types

expr (expression) — extracts a value from the source record:
{
"value": { "kind": "expr", "expr": { "op": "get", "path": ["fieldName"] } },
"target": { "type": "string", "nullable": true, "path": ["destField"] }
}

For nested fields, use a multi-element path:
"path": ["originator", "name", "fullName"]
Do NOT map a parent object when you need a child scalar. str() of a nested object produces Python repr like "{'name': {'fullName': ...}}" — not useful.

const (constant) — injects a fixed value not present in the source:
{
"value": { "kind": "const", "const": { "type": "integer", "value": 100 } },
"target": { "type": "integer", "nullable": false, "path": ["status"] }
}

Use const when:
- The destination requires a field that has no equivalent in the source (e.g., a destination-specific account ID, a fixed status code)
- Source and destination domains are incompatible (e.g., source status is a text string, destination status is a numeric enum — don't map between them, pick the correct
  constant)

const with object type — for structured constants:
{
"value": {
"kind": "const",
"const": { "type": "object", "value": { "objectName": "CheckAccount", "id": "5936402" } }
},
"target": { "type": "object", "nullable": false, "path": ["checkAccount"] }
}
The target type must be "object" — if you set it to "string", the dict gets coerced via str() into a Python repr, not valid JSON.

5. Type Matching Rules

┌────────────────────────┬─────────────┬───────────────────────────────────────────────────────────┐
│      Source data       │ Target type │                          Result                           │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ 42.5 (float)           │ "decimal"   │ Passes through as number                                  │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ 42.5 (float)           │ "string"    │ Coerced to "42.5" — wrong if destination expects a number │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ {"a": 1} (dict)        │ "object"    │ Passes through as JSON object                             │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ {"a": 1} (dict)        │ "string"    │ Coerced to "{'a': 1}" — Python repr, not JSON             │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ "2024-01-01T00:00:00Z" │ "string"    │ Passes through as-is — fine for datetime strings          │
├────────────────────────┼─────────────┼───────────────────────────────────────────────────────────┤
│ "completed" (string)   │ "integer"   │ Will fail or produce garbage — domain mismatch            │
└────────────────────────┴─────────────┴───────────────────────────────────────────────────────────┘

Rule: the target type must match what the destination API/DB actually expects, not what the source produces.

6. source_to_generic Rules

- Only list source fields that are actually used in expr assignments
- Do NOT list source fields that are only used indirectly (parent objects when you extract a child)
- For nested paths like ["originator", "name", "fullName"], use the dotted key: "originator.name.fullName"
- Fields used only in const assignments do not appear here
- The generic_type must match the assignment's target.type

7. generic_to_destination Rules

- Keyed by connection ref (e.g., "conn_2")
- Only list destination fields that appear in assignments' target.path
- destination_type must match the assignment's target.type
- nullable must match the assignment's target.nullable
- Do NOT include fields that were removed from assignments

8. Review Checklist

When reviewing an existing mapping:

1. For each assignment, verify:
   - Does this field exist on the destination for this operation (create vs update)?
   - Is the target type valid and matches what the destination expects?
   - If expr: does the source path resolve to the correct scalar value, not a parent object?
   - If const: is the value appropriate for the destination's domain?
2. For required destination fields, verify:
   - Every required field has a corresponding assignment
   - Required fields have nullable: false
3. For response-only fields (like id, objectName, create, update on create endpoints):
   - They are NOT included in assignments
4. Cross-domain field mapping:
   - Source and destination values are semantically compatible
   - If not compatible (e.g., text status vs numeric enum), use a const instead
5. Three-way sync:
   - Every expr assignment's source field appears in source_to_generic
   - Every assignment's target field appears in generic_to_destination
   - Types and nullability are consistent across all three sections
   - No orphan entries in source_to_generic or generic_to_destination

9. The endpoint_schema is Not Authoritative for Input

The endpoint_schema in the config often describes the response schema, not the request body. Always cross-reference with the actual API documentation to determine:
- Which fields are accepted on input
- Which fields are returned only in responses
- Required vs optional for the specific HTTP method