# BT-050 — Implement AI Workspace Review and Evaluation Contract

## Task ID

`BT-050` — Status: `Proposed`

## Title

Implement Stable AI Workspace Review, Evaluation, and Rework APIs

## Related Specification(s)

- UI-011A AI Collection Workspace Specification.
- UI-011B stable Item review state machine and read model.

## Goal

Expose a dataset-adaptable review queue and detail contract that separates raw
AI evidence, human evaluation, final selection, and system-managed history.

## Scope

- Queue filters and detail read model with Album, model configuration snapshot,
  analysis, recommendations, Photo evidence, runtime metrics, and traceability links.
- `ReadyForReview`, `InReview`, `Approved`, `Rejected`, and `ReworkRequested` decisions.
- Admin rating, notes, selected Album name, reviewer identity/timestamps, version,
  immutable decision evidence, and rework reason.
- Role guards, allowed actions, optimistic version checks, and Operation/Issue links.

## Out of Scope

- Multiple simultaneous administrator assignment/merge workflows.
- Album Promotion, owned by BT-051.

## Dependencies

- BT-044, BT-046, BT-047, and BT-049.
- Approved UI-011B state/field ownership table.

## Implementation Steps

1. Implement stable queue/detail repository projections and permitted-action calculation.
2. Implement review decision commands with immutable AI output and version guards.
3. Add every valid/invalid transition, role, stale-write, rework, and audit test.

## Acceptance Criteria

- Reviewers cannot edit raw AI output, configuration snapshot, Manifest, or system evidence.
- Approval freezes exactly one selected recommendation or approved human revision.
- Reject creates no permanent Album mutation; Rework retains the prior attempt and reason.
- A stale version never overwrites a newer decision and returns structured conflict data.

## Verification

- Generated transition-table tests, repository/API read-model tests, and full regression.

## Risks or Notes

- The current single-administrator deployment does not require assignment or
  merge UX, but the version field preserves a safe future concurrency boundary.
