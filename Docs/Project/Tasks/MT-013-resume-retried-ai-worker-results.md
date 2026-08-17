# MT-013 — Resume Retried AI Worker Results

## Task ID

`MT-013` — Status: `Complete`

## Title

Resume a Failed Work Item From Its Last Accepted Result Stage

## Goal

Allow an Administrator to Retry a Work Item that failed after Vision without
causing a conflicting immutable Vision replay.

## Scope

- Extend the successful Worker claim response with a result-stage recovery
  context.
- Return `AwaitingVision` for a Work Item without an accepted Vision result.
- Return `AwaitingWriter` plus the immutable accepted Vision payload after
  Vision succeeded and Writer failed.
- Make the Worker skip evidence transfer, Vision inference, and Vision
  submission when resuming `AwaitingWriter`.
- Re-run Writer from the accepted Vision payload and preserve the ordinary
  heartbeat, Manifest revalidation, failure, and completion contracts.
- Reject incomplete or unsupported recovery context instead of guessing.
- Add Backend, Worker, API-contract, and operator documentation coverage.

## Out of Scope

- Deleting, replacing, or mutating an accepted result stage.
- Making conflicting result replay acceptable.
- Automatically retrying Failed Work Items without an Administrator action.
- Changing the immutable Evidence Manifest or configuration snapshot.

## Runtime Contract

1. Retry changes only Work Item run state from Failed to Pending.
2. The next atomic claim includes `result_state`.
3. `AwaitingVision` follows the complete Vision → Writer path.
4. `AwaitingWriter` includes `accepted_vision` and follows only the Writer path.
5. The Worker still asks Backend to revalidate the immutable Manifest before
   continuing.
6. Missing accepted Vision for `AwaitingWriter`, or any unsupported stage,
   fails truthfully and never submits a replacement Vision.
7. Backend replay protection remains unchanged and continues returning 409 for
   a genuinely different result submitted to an already accepted stage.

## Acceptance Criteria

- A new Work Item claim reports `AwaitingVision` and no accepted payload.
- A Writer-failed Work Item retains its accepted Vision across Retry.
- Its next claim reports `AwaitingWriter` and the exact normalized Vision
  payload stored by Backend.
- The resumed Worker performs no evidence download, Vision inference, or Vision
  submission.
- Writer receives the accepted Vision and can complete the same Work Item.
- Existing claim ownership, lease, result immutability, and conflict tests pass.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker`
- Targeted Backend Work Item and result submission contract tests.
- Full Backend service regression.
- Manual sequence: Vision accepted → Writer Failed → Admin Retry → claim reports
  AwaitingWriter → Writer accepted → ReadyForReview.

## Completion Record

- Added claim-bound result recovery context without exposing claim Tokens or
  mutable server state.
- Added stage-aware Worker resume behavior and regression coverage.
- Updated the API specification and Chinese Worker manual on 2026-08-17.
