# Pagination

Authoring patterns for `operations.read.pagination` in API endpoints.
Each style is a discriminated branch on `type`.

## `offset`

Fixed-size pages addressed by an integer offset. The endpoint adds
`offset` and `limit` query params; the runtime increments `offset` by
the page size until the response page is empty (or `stop_when` fires).

```json
{
  "type": "offset",
  "offset": { "param": "offset", "initial": 0, "increment_by": 100 },
  "limit":  { "param": "limit", "default": 100, "max": 100 },
  "stop_when": "page_empty"
}
```

## `page`

Pages addressed by a 1-based page number.

```json
{
  "type": "page",
  "page":  { "param": "page", "initial": 1, "increment_by": 1 },
  "limit": { "param": "per_page", "default": 50 },
  "stop_when": "page_empty"
}
```

## `cursor`

Server returns an opaque token in each response; the next request passes
it back. Common with modern APIs (Stripe, Slack, etc.).

```json
{
  "type": "cursor",
  "cursor": { "param": "starting_after", "next_cursor": { "ref": "response.body.next_cursor" } },
  "limit": { "param": "limit", "default": 100 },
  "stop_when": "no_next_cursor"
}
```

## `link`

The next page URL is in a response header (`Link: <…>; rel="next"`) or a
field. The runtime follows the URL until exhausted.

```json
{
  "type": "link",
  "next_link": { "ref": "response.headers.link" },
  "rel": "next",
  "stop_when": "no_next_link"
}
```

## `keyset`

Cursor-style pagination where the cursor is a value from the last record
(e.g. `since_id`). Requires the response records to be ordered.

```json
{
  "type": "keyset",
  "keyset": {
    "param": "since_id",
    "next_cursor": { "ref": "response.body.records[-1].id" }
  },
  "limit": { "param": "limit", "default": 100 },
  "stop_when": "page_empty"
}
```

## Pick the right one

- Offset/page work for older REST APIs where total count or deterministic
  ordering is fine.
- Cursor and link are preferred when available — they're robust to
  insertions during a long sync.
- Keyset is the right choice when the server returns ordered records and
  exposes a stable ordering key.
- Some providers offer multiple pagination modes; use the one with the
  most stable semantics (cursor or link beat offset).
