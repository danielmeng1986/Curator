# UI-011F — Add Work Dispatch Browser Acceptance

## Task ID

`UI-011F` — Status: `Complete`

## Title

Prove Album-Exclusive Work Dispatch in the Browser

## Related Specification(s)

- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- UI-011E Admin Album Work Dispatch Console.

## Goal

Prove that Admin browser actions create one safe Album reservation and visible
work history while concurrent or cross-Worker duplicate dispatch is rejected.

## Scope

- Filter/select/preview/execute happy path with multiple Albums and configurations.
- Available-to-Active UI movement, Batch/Group/Operation links, role denial,
  stale preview, concurrent reservation conflict, terminal release, and redispatch.
- Assertions that Album Status is unchanged by dispatch and history is retained.

## Out of Scope

- Real model quality or production filesystem data.
- Full result/review/Promotion browser journey owned by UI-011D.

## Dependencies

- UI-011E, BT-057, and disposable browser/backend Worker fixtures.

## Implementation Steps

1. Extend disposable fixtures with two Worker kinds and multi-config AI dispatch.
2. Implement happy, authorization, stale, race, release, and redispatch scenarios.
3. Run the suite repeatedly from clean temporary roots and register readiness evidence.

## Acceptance Criteria

- One Album cannot appear in two active Groups, including across Worker kinds.
- Multi-config comparison remains one Group and one reservation.
- Failed/stale dispatch leaves no partial work and the Album remains available.
- Successful dispatch leaves Album Status unchanged and moves it to Active work.
- Release returns it to Available while preserving History.

## Verification

- Browser workflow suite twice from clean fixtures.
- Backend dispatch workflow suite and complete UI regression.

## Risks or Notes

- Concurrency must be proved against the Backend invariant, not only by disabled UI controls.

## Completion Record

- Activated the disposable `future-ai-workspace` scenario with three Albums,
  two model configurations, and a fixture-only second Worker adapter.
- Browser acceptance proves Admin-only access, multi-Album/multi-configuration
  dispatch, one Group per Album, one reservation per Group, unchanged Album
  Status, and Available-to-Active movement.
- A competing Preview/execute race proves the stale browser action is rejected
  without partial work. The active reservation also removes the same Album from
  the second Worker kind's Available view.
- Terminal Group cancellation releases each reservation, restores all Albums to
  Available, and retains four historical Groups including the race scenario.
- The browser suite passed twice from distinct clean temporary roots; fixture
  self-tests, the four-scenario Backend AI Workspace suite, and redaction/cleanup
  assertions also passed.
