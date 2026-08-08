# BT-037 — Complete Operation History Query and Pagination Contract

## Task ID

`BT-037` — Status: `Complete`

## Title

Complete Stable Operation History Query and Pagination

## Related Specification(s)

- [Operation Logging](../Specifications/Operation-Logging.md).
- [API Specification](../Specifications/API-Specification.md).
- [Testing Strategy](../Testing-Strategy.md).

## Goal

Provide a bounded, deterministic, role-safe Operation history API that the Web
management client can filter and paginate without duplicates or omissions when
new Operations are created concurrently.

## Scope

- Filter by exact Operation status and type and inclusive started-at date range.
- Sort deterministically by `started_at DESC, id DESC`.
- Return the standard collection envelope with total, `has_more`, and an opaque
  keyset cursor bound to the active filters.
- Reject malformed, expired-shape, or filter-mismatched cursors with structured
  `400 REQUEST_INVALID` errors.
- Preserve BT-030 role-sensitive projections on every page.

## Out of Scope

- Full-text search over summaries or diagnostics.
- Editing or deleting immutable Operation history.
- Issue, Repair, Snapshot, or Quarantine mutation endpoints.

## Dependencies

- `BT-003` shared versioned API collection contract.
- `BT-027` durable Operation lifecycle.
- `BT-030` role-sensitive Operation disclosure.

## Implementation Steps

1. Specify query parameters, stable ordering, cursor identity, and error behavior.
2. Add repository keyset query/count behavior and role-safe service projection.
3. Return the standard collection envelope from the versioned route.
4. Add repository and authenticated API tests for filtering, page boundaries,
   concurrent inserts, cursor mismatch, validation, and disclosure.

## Acceptance Criteria

- Status, type, and inclusive date filters compose predictably.
- Paging a fixed query never repeats or skips records when a newer record is inserted.
- A cursor cannot silently be reused with different filters.
- Reader, Writer, and Admin projections retain their approved disclosure boundaries.
- Invalid limits, dates, filters, and cursors return structured `400` responses.

## Verification

- Run focused repository/service/API Operation tests.
- Run complete Backend regression.
- Run UI-007 browser acceptance after integration.

## Risks or Notes

- The database row ID participates only in server-side ordering and the opaque
  cursor; it is never exposed as public Operation identity.

## Completion Record

- Added composable status, type, and inclusive UTC date filters with strict
  request validation.
- Added deterministic `started_at DESC, id DESC` repository queries, filtered
  totals, and query-bound opaque keyset cursors.
- Standardized the route on the versioned collection envelope while preserving
  BT-030 Reader/Writer/Admin projections.
- Verified concurrent insertion between pages, filter mismatch, malformed
  input, disclosure, complete Backend regression, and browser-fixture compatibility.
