# UI-006 — Adapt Import Workflow UI

## Task ID

`UI-006` — Status: `Proposed`

## Title

Adapt Import Preview and Execution UI

## Related Specification(s)

- [UI Direct Album Import](../05_Direct_Album_Import.md).
- [Import Workflow](../../Backend/Specifications/Import-Workflow.md).
- [Canonical Path Rules](../../Backend/Specifications/Canonical-Path-Rules.md).

## Goal

Provide a safe staged UI for previewing and executing COPY, MOVE, and
database-only imports with truthful per-item and Operation outcomes.

## Scope

- Source input/discovery, parsed mappings, canonical destinations, warnings, conflicts, and selectable valid items.
- Explicit mode and source-retention semantics, confirmation, execution progress, partial results, and Operation navigation.
- Inline Model/Studio creation only where the approved Import contract permits it.
- `NeedsRepair` presentation without client-side repair decisions.

## Out of Scope

- Issue/Repair decisions, handled by UI-008.
- Direct browser filesystem access outside Backend-controlled configured roots.

## Dependencies

- UI-002, UI-003, and supported authenticated Import preview/execute APIs.
- UI-007 for final Operation-detail linking; a temporary stable Operation link contract may precede its page.

## Implementation Steps

1. Reconcile current Import fields and modes with Backend preview/execute contracts.
2. Implement the review grid, selection, confirmation, progress, and result states.
3. Add contract tests for zero-write preview, payload identity, partial failure, and duplicate submission.

## Acceptance Criteria

- Preview makes no database or filesystem mutation and clearly separates errors from warnings.
- Execution uses the reviewed preview identity/version; changed or stale input requires re-preview.
- COPY, MOVE, and database-only consequences are named before confirmation.
- Per-item and aggregate results match durable Backend state; failures never claim rollback or success incorrectly.

## Verification

- Run Web contract tests and Backend import workflow-readiness tests.
- UI-013 supplies filesystem-backed browser acceptance with disposable roots.

## Risks or Notes

- Browser tests must assert filesystem outcomes through disposable fixtures, not only visible success text.
