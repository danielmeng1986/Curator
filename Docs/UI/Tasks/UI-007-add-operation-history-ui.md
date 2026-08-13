# UI-007 — Add Operation History UI

## Task ID

`UI-007` — Status: `Complete`

## Title

Add Role-Sensitive Operation History and Traceability UI

## Related Specification(s)

- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).
- [Issue Management](../../Backend/Specifications/Issue-Management.md).
- [UI Specification](../Specification.md).

## Goal

Make durable workflow outcomes and cross-workflow links navigable while
enforcing role-sensitive diagnostic disclosure.

## Scope

- Operation list, filters, pagination, public status/type/summary, and detail.
- Links among Import, Issue, Repair, Snapshot, authentication, Quarantine, and affected entities.
- Reader public summaries and authorized Writer/Admin recovery context.
- Operation links from mutation result feedback.

## Out of Scope

- Editing/deleting Operation history or exposing raw logs and exception dumps.
- Performing Repair or administrative actions directly in this task.

## Dependencies

- UI-002 and role-sensitive Operation API disclosure from BT-030.
- Stable public identifiers for linked records.

## Implementation Steps

1. Define list/detail read models and allowed fields by role.
2. Build routes, filters, detail sections, and cross-workflow navigation.
3. Add disclosure and broken/missing-link client tests.

## Acceptance Criteria

- Operation records are read-only and their displayed outcome matches durable state.
- Reader never receives or renders sensitive diagnostics; Writer/Admin see only contract-authorized context.
- Each supported linked entity is navigable or explicitly described as unavailable/retired.
- UI handles archived or missing related entities without discarding the Operation evidence.

## Verification

- Run Operation API disclosure tests and Web client contract tests.
- UI-015 verifies browser-level role disclosure.

## Risks or Notes

- Absolute filesystem paths and secret-bearing error strings require Backend-side redaction before serialization.

## Completion Notes

- Added a read-only Operation list with status, type, and inclusive date filters,
  stable cursor navigation, totals, and durable status summaries.
- Added role-safe detail rendering and links to related Operations, Issues, and
  Repairs; retained identifiers without a supported detail route are explicitly
  marked unavailable.
- Import results now land on a functional Operation detail route.
- Focused Writer/Reader browser acceptance verifies traceability and that no
  sensitive diagnostic path is rendered.
