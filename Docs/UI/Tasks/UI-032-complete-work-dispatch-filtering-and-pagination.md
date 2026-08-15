# UI-032 — Complete Work Dispatch Filtering and Pagination

## Task ID

`UI-032` — Status: `Complete`

## Title

Add Status-Centered Album Filtering and Pagination to Work Dispatch

## Related Specification(s)

- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- `BT-032` Album query contract.
- `BT-055` dispatch candidate and preview contract.
- `UI-011E` filtered Album Work Dispatch UI.

## Goal

Make large Album collections operable in Work Dispatch by prioritizing Status,
Studio, and Model filters and by exposing the Backend's existing bounded
pagination instead of silently loading at most 100 Albums.

## Scope

- Status, Studio, and Album Model filters in the Available candidate view,
  reusing the established entity option labels from Album management.
- Removal of Album-title search from the primary Dispatch workflow; no Backend
  removal of the reusable `q` query contract is required.
- Explicit page size, offset, total count, current-page range, previous, and next
  controls for Available candidates.
- Independent pagination for Active and History Group views using their existing
  `limit`, `offset`, and `total` contract.
- Stable filter and page state during refreshes and recoverable workflow
  navigation where supported by the application route-state convention.
- Precise selection semantics for current-page selection and bounded filtered
  first-`N` selection.
- Focused UI contract tests and real-browser acceptance with more records than
  one page.

## Out of Scope

- New Backend candidate filters or changes to Album query semantics.
- Free-text title search as a primary Dispatch control.
- Unbounded select-all or dispatch-all behavior.
- Changing Album Status during Dispatch.
- Device targeting, Worker capability routing, or model-file compatibility.
- Redesigning the Active and History Group read models beyond pagination.

## Dependencies

- `BT-032` and `BT-055` — Status, Studio, Model, limit, offset, total, and bounded
  preview semantics already exposed by the Backend.
- `UI-005` — reusable Album filter option loading and labels.
- `UI-011E`, `UI-011F`, and `UI-030` — existing Dispatch interaction, browser
  acceptance, and run-progress presentation.

## Product and Interaction Contract

1. Available defaults to Backend-declared available Albums and offers Status,
   Studio, and Model selectors as the primary filters.
2. Applying or clearing any filter resets the Available offset to zero.
3. Pagination displays the current visible range and total matching count, with
   unavailable previous/next actions disabled.
4. Page size is bounded by the Backend contract and defaults to 50 Albums.
5. `Select current page` selects only eligible Albums visible on that page.
6. `Select first N` means the first `N` eligible Albums in the complete current
   filtered and sorted result, not merely the rows currently loaded in the
   browser. It uses the Backend preview `filters` plus `first_n` contract and
   remains bounded to 100.
7. Manual checkbox selection remains explicit-ID selection and is cleared when
   filters, sort, page size, page, Worker kind, or view changes, preventing hidden
   stale selections.
8. Active and History views show their own total and page controls; navigating
   between views does not reuse an incompatible offset.
9. Empty pages distinguish “no Albums match these filters” from “no Albums are
   available for this Worker”.
10. Dispatch continues to disclose that Album Status is not changed.

## Implementation Steps

1. Reuse Status, Studio, and Model option loaders and add explicit list state for
   filters, sort, limit, and per-view offset.
2. Pass filters, limit, and offset to candidate requests and retain collection
   metadata instead of discarding `total`.
3. Add shared bounded pagination controls to Available, Active, and History.
4. Separate manual/current-page selection from server-resolved filtered first-`N`
   preview so their semantics are accurate across pages.
5. Preserve or reset view state according to the interaction contract and make
   selection invalidation visible.
6. Extend component and Playwright coverage with multiple pages, filter changes,
   empty results, boundary pages, and first-`N` spanning pages.

## Acceptance Criteria

- An Administrator can filter candidate Albums independently by Status, Studio,
  and Model without entering an Album title.
- A result set larger than one page exposes its total and can be navigated without
  duplicate or skipped rows under a stable sort.
- Filter changes return to the first page and never dispatch previously hidden
  manual selections.
- `Select current page` and filtered `Select first N` behave according to their
  disclosed, distinct semantics, including when `N` crosses a page boundary.
- Available, Active, and History views all expose correct bounded pagination and
  independent offsets.
- Loading, empty, error, stale-preview, and reservation-conflict states remain
  actionable.
- Reader and Writer principals remain unable to access the Admin Dispatch route
  or its APIs.

## Verification

- UI contract tests for query construction, state reset, collection metadata,
  page boundaries, and selection invalidation.
- Backend contract regression confirming Status, Studio, Model, stable sort,
  limit, offset, total, and first-`N` preview behavior.
- Playwright acceptance with more than 50 candidate Albums and more than one page
  of Active or History Groups.
- Existing Work Dispatch execution, conflict, review, and permission suites.

## Risks or Notes

- Offset pagination assumes a stable explicit sort. Concurrent Album changes can
  still move rows between pages; Preview's signed state and conflict checks remain
  the material-action safety boundary.
- The Album `model_id` filter refers to a Model/person linked to an Album. It is
  distinct from the AI Model Configuration selected for inference.

## Completion Record

- Replaced Album-title search with Status, Studio, and Album Model filters.
- Added independent bounded pagination, totals, range disclosure, and page-size
  controls for Available, Active, and History views.
- Added safe selection invalidation on filter, page, view, and Worker changes;
  current-page selection remains explicit while filtered first-N selection can
  cross page boundaries through the Backend contract.
- Added collection metadata adaptation, a 55-Album disposable scenario, focused
  contract/browser coverage, and regression coverage through UI readiness.
- Completed on 2026-08-15; the full 15-suite UI readiness gate passed.
