# UI-035 — Separate Work Queue, Review, and Item Cancellation

## Task ID

`UI-035` — Status: `Complete`

## Title

Cancel Failed Work Items Individually and Separate Worker Work From Review

## Goal

Keep large Work Dispatch queues operable by allowing a failed run to be
cancelled without abandoning its Group, separating terminal execution from
Worker work, and exposing pagination at both ends of long pages.

## Scope

- Add a confirmed Cancel action beside Retry for a Failed Work Item.
- Reuse the existing versioned Work Item Cancel API; preserve the Dispatch
  Group, its other runs, reservation, and audit history.
- Rename Active to Worker Queue and show only Active Groups containing Pending,
  Claimed, or Failed Work Items.
- Add Review between Worker Queue and Closure for Groups with ReadyForReview,
  InReview, or ReworkRequested work and no remaining Worker execution.
- Add Closure before History for Approved, Rejected, fully Cancelled, and other
  terminal Active Groups that now need Promotion, release, or closure.
- Add identical First/Previous/Next/Last and direct page-number navigation above
  and below every Dispatch view.
- Keep independent limit and offset state for Available, Worker Queue, Review,
  Closure, and History.
- Preserve Worker Queue auto-refresh and update both pagination controls during
  polling.

## Out of Scope

- Cancelling a currently Claimed Work Item.
- Automatically cancelling all runs in a Group.
- Releasing the Album reservation when one Work Item is cancelled.
- Replacing the dedicated AI Reviews workflow.
- Changing immutable result, review, or Promotion history.

## Product Contract

1. A Failed row offers Open, Retry, and Cancel.
2. Cancel requires explicit confirmation and sends the current item version.
3. Successful Cancel changes only that Work Item to Cancelled; it never invokes
   Group Abandon.
4. Worker Queue contains Groups with at least one Pending, Claimed, or Failed
   run.
5. Review contains unreleased Groups with open human-review work and no remaining
   Worker run.
6. Closure contains unreleased Groups with neither Worker nor open-review work.
7. History continues to contain Released Groups.
8. Every list renders the same bounded range, page number, First, Previous,
   direct page input, Go, Next, and Last controls before and after its content.

## Acceptance Criteria

- `EVIDENCE_SAMPLE_INSUFFICIENT` and other Failed Work Items can be cancelled
  individually from Group detail or the queue.
- Other Work Items and the Group remain unchanged.
- A sole cancelled run leaves Worker Queue and appears in Closure,
  where the Group can be released.
- ReadyForReview and Approved Groups no longer clutter Worker Queue.
- Page sizes 50 and 100 remain navigable without scrolling to the bottom first.
- Backend, UI contract, browser acceptance, permission, and workflow regression
  suites pass.

## Verification

- Backend Work Item cancellation and Group view partition tests.
- Work Dispatch UI contract tests for Cancel, four tabs, and dual pagination.
- Browser acceptance covering Failed → Cancelled without Group abandonment.
- Existing Work Dispatch and AI review regression suites.

## Completion Record

- Added versioned per-item Failed cancellation to Work Dispatch.
- Split active execution into Worker Queue, Review, and Closure projections.
- Added synchronized top and bottom pagination on 2026-08-18.
