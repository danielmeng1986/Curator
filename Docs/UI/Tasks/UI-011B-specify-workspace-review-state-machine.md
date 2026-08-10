# UI-011B — Specify Workspace Review State Machine

## Task ID

`UI-011B` — Status: `Proposed`

## Title

Specify the Stable Workspace Review State Machine and Read Model

## Related Specification(s)

- UI-011A approved AI Collection Workspace Specification.
- [Workspace Workflow](../../Backend/Specifications/Workspace-Workflow.md), state-transition safety principles.

## Goal

Define dataset-independent review states, fixed approval fields, transitions,
concurrency, and a stable UI read model that can survive underlying table changes.

## Scope

- Proposed lifecycle: collecting, ready for review, in review, approved/rejected, promoted, archived; final names require approval.
- Submission/reviewer/decision timestamps, reviewer, decision, notes, version, Promotion target, and Operation identifiers.
- Allowed actors, editable fields, transition guards, idempotency, stale-write handling, and immutable terminal evidence.
- Dataset adapter boundary for variable AI result fields.
- Relationship among Album Reservation/Group lifecycle, Work Item run state,
  review state, Promotion, Group closure, and release.

## Out of Scope

- Dataset-specific field mapping or UI implementation.
- Reusing historical table state values without review.

## Dependencies

- UI-011A.

## Implementation Steps

1. Specify states, transitions, actors, invariants, and invalid-state outcomes.
2. Define the stable queue/detail read model and versioned mutation commands.
3. Create Backend state-machine/API tasks with unit, repository, and workflow acceptance requirements.

## Acceptance Criteria

- Every state has a clear owner, allowed mutations, entry condition, and exit outcome.
- Invalid and stale transitions are rejected before mutation and are idempotent where specified.
- Approval freezes the specified final selection; Promotion cannot create duplicate permanent entities.
- Stable review fields do not depend on a particular dataset table layout.
- Review or individual Work Item completion cannot prematurely release the
  Album; every state identifies whether the Group still owns its reservation.

## Verification

- State-transition table review plus generated happy/invalid path test inventory.
- Confirm UI-011C can render the contract without direct table knowledge.

## Risks or Notes

- Approval and Promotion may be separate steps; the Specification must decide rather than letting UI behavior imply the answer.
