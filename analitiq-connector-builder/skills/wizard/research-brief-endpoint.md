# API Endpoint Research Brief

Research the following API endpoint and answer every question below. Use official documentation as the primary source.

## System
- **Name:** {system_name}
- **Documentation URL:** {url, if provided}
- **Base URL:** {base_url}

## Endpoint
- **Path:** {endpoint_path} (e.g., `/v1/transfers`)
- **Method:** {method} (e.g., `GET`)

## Questions

### Deprecation
1. Is this endpoint deprecated or scheduled for sunset? If so, what is the recommended replacement endpoint?

### Response Schema
2. What is the full response structure? Include all fields with types, descriptions, and nullability.
3. Is the response a single object or an array of objects?
4. Are there nested objects or arrays in the response?
5. Which fields are required vs optional?

### Filters / Query Parameters
6. What query parameters does this endpoint accept for filtering?
7. For each filter: name, type, operators (eq, gte, lte, in, like), required, example value

### Pagination
8. How does this endpoint paginate? (offset, cursor, page number, link header)
9. What are the pagination parameter names? (limit, offset, page, cursor, next token field)
10. Is there a maximum page size?

### Incremental Sync
11. Which response field represents "last modified" or "created" time?
12. Which filter parameter accepts that timestamp for incremental fetching?

## Expected Output Format

```json
{
  "source_url": "https://docs.example.com/api/v1/transfers",
  "deprecated": false,
  "endpoint": "/v1/transfers",
  "method": "GET",
  "endpoint_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "...",
    "description": "...",
    "type": "array",
    "items": {
      "type": "object",
      "properties": { "...": "..." }
    }
  },
  "filters": { "...": "..." },
  "pagination": { "type": "offset", "params": { "...": "..." } },
  "replication_filter_mapping": { "...": "..." }
}
```
