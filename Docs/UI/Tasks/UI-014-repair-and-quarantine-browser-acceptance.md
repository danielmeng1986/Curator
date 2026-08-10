# UI-014 — Add Repair and Quarantine Browser Acceptance

## Task ID

`UI-014` — Status: `Complete`

## Title

Add Issue, Repair, and Quarantine Browser Acceptance

## Related Specification(s)

- [Repair Workflow](../../Backend/Specifications/Repair-Workflow.md).
- [Issue Management](../../Backend/Specifications/Issue-Management.md).

## Goal

Prove end-to-end Issue review, Repair decisions, suppression, Quarantine, and
item Restore safety through role-appropriate UI journeys.

## Scope

- Continue from a failed Import to linked Issue/Repair evidence.
- Safe automatic, assisted, and manual decisions; accept/reject/suppress; ownership and status transitions.
- Quarantine and filesystem item Restore success and specified failure paths.
- Durable Operation/Issue/Repair/filesystem assertions.

## Out of Scope

- Database Snapshot Restore and exhaustive Service policy branch testing.

## Dependencies

- UI-003, UI-007, UI-008, UI-009, and UI-010.

## Implementation Steps

1. Map browser journeys to existing Backend repair-policy, decision, quarantine, and traceability evidence.
2. Implement role-separated scenarios and filesystem assertions.
3. Run twice with sanitized artifacts and verify no shared Quarantine state.

## Acceptance Criteria

- UI never executes a Repair action not offered by the Backend policy response.
- Required manual confirmation cannot be bypassed by client payload manipulation.
- Invalid/replayed/unauthorized decisions preserve exact prior database and filesystem state.
- Quarantine and Restore results are verified and linked through durable history.

## Verification

- Run browser suite twice, then Backend repair, quarantine, decision, and traceability workflow acceptance.

## Risks or Notes

- Ensure the word “Restore” is visibly distinguished from database Restore in UI copy and tests.

## Completion Record

- Added role-separated Chromium journeys from a failed Import Operation through
  its linked Issue and Repair evidence, including durable decision Operations.
- Proved Issue assignment, begin-work, resolution, stale decision rejection,
  Reader redaction, and Writer/Admin decision boundaries.
- Proved assisted/manual confirmation cannot be bypassed, failed verification
  remains unresolved, later verified repair resolves, and ignore/suppression
  policy remains Backend-owned and role-bounded.
- Proved Quarantine cancellation, Admin-only execution, intact inventory,
  Preview replay rejection, restore collision/staleness, Snapshot creation,
  successful item Restore, and linked Quarantine/Restore Operations.
- The complete browser suite passed twice from clean disposable roots. Import,
  Repair policy/decision, Quarantine, and cross-workflow traceability Backend
  acceptance passed on 2026-08-11.
