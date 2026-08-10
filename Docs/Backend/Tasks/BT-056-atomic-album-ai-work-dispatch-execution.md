# BT-056 — Implement Atomic Album AI Work Dispatch Execution

## Task ID

`BT-056` — Status: `Complete`

## Title

Atomically Reserve Albums and Dispatch AI Work Items

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md), Atomic execution contract.
- [Operation Logging](../Specifications/Operation-Logging.md).

## Goal

Execute one reviewed dispatch batch atomically, reserving every selected Album
and creating its AI comparison Work Items without partial or duplicate work.

## Scope

- Single-use preview execution and complete state revalidation.
- Batch, one Reservation/Group per Album, one Work Item per selected model
  configuration, and durable Operation creation.
- Structured stale, replay, eligibility, uniqueness-race, and failure outcomes.
- Transition active clients away from direct single-Item Admin creation where it
  would bypass Album reservation.

## Out of Scope

- Worker claim/result behavior already owned by BT-046/BT-049.
- Group release and redispatch.

## Dependencies

- BT-054, BT-055, and BT-046.

## Implementation Steps

1. Implement the all-or-nothing service/repository transaction and adapter-owned
   AI Work Item creation.
2. Expose Admin execution and Batch/Group result reads with Operation links.
3. Add replay, stale, concurrent cross-Worker, rollback, and multi-config tests.

## Acceptance Criteria

- Success creates the complete reviewed graph exactly once and does not change Album Status.
- Any selected Album conflict prevents the entire batch with no partial records.
- Concurrent attempts cannot create two active reservations for one Album.
- Multiple configurations create several Work Items beneath one Group/reservation.

## Verification

- Database race and injected-rollback tests.
- Authenticated API and Operation traceability tests.
- Complete Backend regression.

## Risks or Notes

- Direct Admin Work Item creation must not remain an alternative path that
  bypasses reservation invariants.

## Completion Record

- Added migration `0007_work_dispatch_execution.sql` with a durable unique
  successful Preview claim linked to its resulting Batch.
- Added the Album-analysis dispatch adapter transaction. It revalidates the
  Workspace, model configurations, Album identities/versions, and Reservation
  absence, then atomically creates the Preview claim, Batch, one Group and
  Reservation per Album, all configuration-specific AI Work Items and Group
  links, and one successful Operation.
- Added Admin-only `POST /api/v1/work-dispatch/execute` and Batch detail reads.
  Successful execution returns Batch, Operation, Group, Album, and Work Item
  identities for direct UI navigation.
- Retired direct Admin creation through `/api/v1/ai-workspaces/{uuid}/items`
  with `409 WORK_DISPATCH_REQUIRED`; Worker Claim/heartbeat/failure/retry
  continues against the atomically dispatched Items.
- Verified all-or-nothing behavior for stale Albums, active Reservation races,
  concurrent execution of one Preview, replay, and injected mid-batch failure.
  Multiple configurations remain inside one Group and Album Status is unchanged.
- Verification: 5 focused atomic migration/service/API tests passed and the
  complete Backend regression passed all 717 tests.
