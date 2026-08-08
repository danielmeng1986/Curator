# UI-013 — Add Import Browser Acceptance

## Task ID

`UI-013` — Status: `Proposed`

## Title

Add Import Workflow Browser Acceptance

## Related Specification(s)

- [Import Workflow](../../Backend/Specifications/Import-Workflow.md).
- [UI Direct Album Import](../05_Direct_Album_Import.md).

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

