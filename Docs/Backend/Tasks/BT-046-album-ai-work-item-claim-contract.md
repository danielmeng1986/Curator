# BT-046 — Implement Album AI Work Item and Claim Contract

## Task ID

`BT-046` — Status: `Complete`

## Title

Implement Album AI Work Items, Worker Claims, and Retry Safety

## Related Specification(s)

- UI-011A AI Collection Workspace Specification.
- UI-011B Item run/review/promotion state model.
- [Authentication](../Specifications/Authentication.md).

## Goal

Persist one `workspace_album_ai_worker` Item for one Album/model-configuration
run and provide safe queue, claim, lease, retry, and failure semantics.

## Scope

- Item identity, Workspace/Album/configuration links, configuration snapshot,
  run state, attempt, Worker Token identity, lease, timestamps, version, and evidence links.
- Multiple configurations and runs for the same Album.
- Writer claim/heartbeat/fail commands with atomic ownership. Successful
  completion is reserved for BT-049 so validated result submission and the
  terminal state change occur atomically.
- Admin creation/cancellation/retry and truthful Operation/Issue evidence.

## Out of Scope

- Photo selection/content, result JSON, review decisions, and Promotion.
- Multi-Worker distributed scheduling beyond bounded leases and atomic claims.

## Dependencies

- BT-044 and BT-045.
- Approved UI-011B run-state transitions.

## Implementation Steps

1. Add schema and repository transaction boundaries for Items and leases.
2. Implement Admin queueing plus Writer claim, heartbeat, failure, expiry, and retry APIs.
3. Add concurrency, replay, lease-expiry, cancellation, and Operation tests.

## Acceptance Criteria

- At most one unexpired Worker claim owns an Item at a time.
- A Writer cannot mutate an Item it has not claimed.
- Retry preserves earlier attempt evidence and creates no ambiguous success.
- Archived/Closed Workspace rules prevent prohibited new work.

## Verification

- Atomic claim race tests, API authorization tests, failure injection, and full regression.

## Risks or Notes

- Human review concurrency is deferred, but Worker duplicate execution must be
  prevented in the first implementation.

## Completion Record

- Added migration `0005_album_ai_work_item.sql` with durable Work Items,
  bounded leases, optimistic versions, and separate per-attempt history.
- Added Admin queue/retry/cancel APIs and Writer-only claim/heartbeat/fail APIs.
  Claim and lease-expiry recovery are atomic, and ownership is enforced for
  every Worker mutation.
- Captured the selected model configuration snapshot on every Item so later
  configuration edits cannot change the meaning of an existing run.
- Extended the remote AI Worker client to use the authenticated REST contract;
  it does not receive database access.
- Kept successful completion out of this task intentionally: BT-049 will bind
  schema-validated two-stage results and the `Completed` transition in one
  transaction.
- Verification: focused repository/service/API/Worker tests passed; the full
  backend regression passed all 700 tests.
