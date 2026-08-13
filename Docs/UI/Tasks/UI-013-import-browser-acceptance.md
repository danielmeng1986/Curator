# UI-013 — Add Import Browser Acceptance

## Task ID

`UI-013` — Status: `Complete`

## Title

Add Import Workflow Browser Acceptance

## Related Specification(s)

- [Import Workflow](../../Backend/Specifications/Import-Workflow.md).
- [UI Direct Album Import](../Features/Direct-Album-Import.md).

## Goal

Prove staged Import behavior, filesystem truth, and durable Operation outcomes
through the UI for all supported execution modes.

## Scope

- Zero-write preview; COPY, MOVE, and database-only success.
- Validation, duplicate/canonical-path collision, stale preview, cancellation, duplicate submission, partial failure, and `NeedsRepair` result.
- Album/relationship, source/destination filesystem, Snapshot, and Operation assertions.

## Out of Scope

- Repairing the resulting Issue through the same scenario; UI-014 owns that continuation.

## Dependencies

- UI-003, UI-006, and UI-007.

## Implementation Steps

1. Create isolated source/destination fixtures for each mode and failure stage.
2. Drive Preview, review, confirmation, execution, and result navigation through Playwright.
3. Assert exact durable/filesystem outcomes and run twice from clean roots.

## Acceptance Criteria

- Preview changes no row, file, Snapshot, or material Operation state beyond explicitly specified preview audit.
- Each mode produces exactly the specified source/destination and database result.
- Rejected/stale/cancelled/duplicate actions produce no unintended mutation.
- Partial failure and `NeedsRepair` UI match durable Operation/Issue state without falsely claiming rollback.

## Verification

- Run browser Import suite twice and Backend import workflow-readiness afterward.

## Risks or Notes

- Avoid OS-dependent path assumptions; fixture paths must exercise the canonical path contract explicitly.

## Completion Record

- Added isolated real-Chromium journeys for COPY, MOVE, and DATABASE_ONLY with
  exact source, canonical destination, Album, Album-Model, Snapshot, and
  Operation assertions.
- Proved Preview is zero-write, cancellation preserves state, duplicate batch
  paths and destination collisions cannot execute, and changed sources make a
  reviewed Preview stale without side effects.
- Proved concurrent duplicate submission is blocked in the client and a later
  replay is rejected by the Backend while producing exactly one Album and one
  Import Operation.
- Added an explicitly fixture-only post-persistence filesystem failure and
  proved mixed Succeeded/NeedsRepair UI results, durable Albums, filesystem
  truth, and a NeedsRepair Operation without attempting UI-014 repair work.
- The complete browser suite passed twice from fresh disposable roots and the
  Backend Import workflow readiness suite passed on 2026-08-11. After UI-018
  resolved the pre-existing delayed Album-search navigation race, the complete
  Web regression gate passed with the new Import suite included.
