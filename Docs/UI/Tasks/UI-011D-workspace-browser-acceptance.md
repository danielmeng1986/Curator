# UI-011D — Add Workspace Browser Acceptance

## Task ID

`UI-011D` — Status: `Proposed`

## Title

Add AI Workspace Review Browser Acceptance

## Related Specification(s)

- UI-011A, UI-011B, and UI-011C.
- Approved Backend AI Workspace workflow acceptance tasks.

## Goal

Prove AI Worker submission, human review, decision, Promotion, and archival
outcomes through the UI without touching historical Workspace data.

## Scope

- AI result appears in queue; provenance and field ownership are rendered correctly.
- Human draft/revision, valid and invalid transitions, reject/rework, approval, Promotion, duplicate protection, and archive/read-only behavior.
- Stale concurrent edit and dataset-adapter compatibility scenarios.
- Durable Operation, Issue, Workspace, and permanent-entity assertions.

## Out of Scope

- Testing AI model quality or every dataset field permutation.
- Loading retired `workspace_album` fixtures as active records.

## Dependencies

- UI-003 and completed UI-011A/B/C plus Backend workflow evidence.

## Implementation Steps

1. Map each state transition and failure path to exact UI and durable assertions.
2. Build disposable AI Worker submission and browser review scenarios.
3. Run twice from clean fixtures and verify historical data remains inaccessible.

## Acceptance Criteria

- UI cannot transition a record outside the approved state machine or overwrite a newer version.
- Reject has no permanent-entity side effect; Promotion is idempotent and exactly traceable.
- Archived records are read-only and remain auditable.
- Variable dataset fields do not change the stable review-state semantics.

## Verification

- Run Workspace browser suite twice, Backend Workspace workflow-readiness, and full regression.

## Risks or Notes

- This task remains Blocked until a real first dataset and its disposable fixture are specified.

