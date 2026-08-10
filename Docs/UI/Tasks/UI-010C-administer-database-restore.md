# UI-010C — Administer Database Restore

## Task ID

`UI-010C` — Status: `Complete`

## Title

Add Protected Database Restore Administration

## Related Specification(s)

- [Snapshot Specification](../../Backend/Specifications/Snapshot-Specification.md), restore and recovery requirements.
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Provide an Admin-only database Restore workflow with recovery-point selection,
impact review, protective Snapshot, verified completion, and truthful failure.

## Scope

- Select only verified Backend-listed recovery points.
- Show recovery-point identity/time/reason, expected impact, and required confirmation.
- Create/verify a pre-Restore protective Snapshot, perform Restore, verify database health, and link Operations.
- Prevent duplicate execution and recover safely from interruption.

## Out of Scope

- Uploading arbitrary database files or restoring filesystem media.
- Quarantine item restore, handled by UI-009.

## Dependencies

- UI-010, UI-010B, UI-003, and an authenticated Admin Restore API.
- Approved Specification decision for confirmation strength, service interruption, and post-Restore token/session behavior.

## Implementation Steps

1. Resolve the Restore confirmation, concurrency, protective Snapshot, and session contracts.
2. Implement Backend orchestration and safe progress/result states, then add the Admin UI.
3. Test success and every precheck/Snapshot/Restore/verification/interruption failure stage.

## Acceptance Criteria

- Restore cannot begin without a verified recovery point, usable protective Snapshot, and explicit Admin confirmation.
- A rejected, cancelled, stale, or duplicate request makes no database change.
- Success is claimed only after database verification and truthful Operation persistence.
- After Restore, the UI revalidates its Token and reloads data rather than relying on stale client state.

## Verification

- Run all Restore scenarios against disposable databases and backup roots only.
- Run Backend full regression after successful and simulated-failure recovery cases.

## Risks or Notes

- This is the highest-risk UI mutation and remains Blocked until the confirmation and recovery Specification is explicit.

## Result

- Added an Admin-only selector containing only Backend-listed recovery points
  with a passed verification state.
- Restore uses the Backend-issued exact confirmation phrase and preview token;
  the browser never supplies a path.
- Verified success displays the protective recovery point, clears the current
  browser connection and cached page state, and requires reconnection against
  the restored database.
