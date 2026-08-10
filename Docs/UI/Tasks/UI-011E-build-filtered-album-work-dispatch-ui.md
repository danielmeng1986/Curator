# UI-011E — Build Filtered Album Work Dispatch UI

## Task ID

`UI-011E` — Status: `Complete`

## Title

Build the Admin Album Work Dispatch Console

## Related Specification(s)

- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- UI-011A AI Collection Workspace product/data contract.

## Goal

Let an Admin find currently available Albums, preview a bounded Worker dispatch,
execute it safely, and move directly to the resulting active work.

## Scope

- Available, Active, and History views in the AI Workspace administration area.
- Album filters, manual/current-page/first-`N` selection, Worker kind, Workspace,
  and one-or-more model configuration controls.
- Per-Album eligibility/warnings, dispatch consequences, exact confirmation,
  conflict refresh, Batch result summary, and links to Groups/Operations/review.
- Explicit disclosure that Album Status is not changed by dispatch.

## Out of Scope

- Computing eligibility or looping over single-Item creation in the browser.
- Review/detail UI owned by UI-011C and Worker execution UI.

## Dependencies

- UI-011A, UI-011B, BT-055, and BT-056.
- Shared UI-002 errors/feedback and UI-003 disposable fixtures.

## Implementation Steps

1. Add dispatch navigation and Available/Active/History list states.
2. Build selection, configuration, preview, confirmation, execution, and conflict recovery flows.
3. Add focused component/client tests for roles, filtering, bounds, and structured failures.

## Acceptance Criteria

- The default page shows only Backend-declared available Albums.
- A successful dispatch removes Albums from Available and reveals them in Active
  with Batch, Group, Work Item, Workspace, and Operation links.
- Multiple model configurations are displayed as one Album Group with several runs.
- `400`, `403`, and stale/reservation `409` outcomes are actionable and never displayed as success.

## Verification

- UI client/component tests with Backend fixture responses.
- Backend dispatch contract suite.
- UI-011F browser acceptance.

## Risks or Notes

- Removing a dispatched row without a result summary/link would make successful
  work appear lost; the Active transition is part of acceptance.

## Completion Record

- Added an Admin-only Album Work Dispatch route and Administrator Center entry.
- Implemented Available, Active, and History projections, Worker/Album filters,
  current-page and bounded first-N selection, Workspace and multi-configuration
  controls, zero-write Preview acknowledgement, and token-bound execution.
- Successful execution moves directly to Active Groups and explicitly confirms
  that Album Status was not changed; structured Backend errors remain actionable
  through the shared UI feedback layer.
- Added a focused Work Dispatch UI contract test and retained the Backend
  dispatch contract coverage supplied by BT-054 through BT-058.
