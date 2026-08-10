# UI-018 — Prevent Stale Album List Refresh After Navigation

## Task ID

`UI-018` — Status: `Complete`

## Title

Prevent Stale Album List Refresh After Navigation

## Related Specification(s)

- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md).
- [UI-005](UI-005-adapt-entity-management-ui.md).
- [UI-012](UI-012-entity-management-browser-acceptance.md).

## Goal

Keep Album detail state stable when the user navigates away from a filtered
Album list while a delayed search or list request is still pending.

## Scope

- Cancel pending Album search debounce work when filtering or opening detail.
- Invalidate older Album list requests and discard responses outside the list route.
- Regress search, immediate detail navigation, inline Model creation, and Save.

## Out of Scope

- Changing Album search semantics, Backend filters, or pagination contracts.
- Introducing a general application-wide cancellation framework.

## Dependencies

- UI-005 and UI-012 — provide the affected entity journey and fixtures.

## Implementation Steps

1. Give Album list renders a current request identity and route guard.
2. Own and cancel the delayed search timer at the page-object boundary.
3. Extend the focused entity browser journey past the debounce interval.

## Acceptance Criteria

- A delayed search cannot replace Album detail after navigation.
- An older in-flight list response cannot render outside the Album list route.
- The user can immediately open the filtered Album, edit it, and save normally.
- Normal search, explicit Filter, and pagination continue to work.

## Verification

- Run the UI-005 entity-management browser acceptance twice.
- Run UI-012 permanent entity acceptance and Web contract tests.

## Risks or Notes

- Request invalidation intentionally discards stale presentation results; it does
  not cancel or alter Backend reads, which are side-effect free.

## Completion Record

- Added owned debounce cancellation and monotonically invalidated Album list reads.
- Guarded both successful and failed list responses by active request and route.
- Extended the regression to remain on detail beyond the debounce interval before
  inline Model creation and Save.
