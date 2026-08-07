# BT-021 — Verify Workspace Lifecycle Workflow

## Task ID

`BT-021` — Status: `Proposed`

## Title

Verify Workspace Lifecycle Workflow

## Related Specification(s)

- [Workspace Workflow](../Specifications/Workspace-Workflow.md), Lifecycle state definitions, Lifecycle state machine, Controlled Review Modifications, and Validation and error handling sections.
- [Repository Specification](../Specifications/Repository-Specification.md), workspace persistence contracts.
- [Operation Logging](../Specifications/Operation-Logging.md), workspace promotion and material batch action requirements.

## Goal

Verify that a persisted workspace follows its complete lifecycle across service and repository boundaries and rejects state-incompatible activity without side effects.

## Scope

- Add scenarios for `Active → Review → Active`, `Review → Closed`, and `Closed → Archived / Retired`.
- Verify allowed review changes, rejected state-incompatible operations, persisted historical state, and read-only behavior after closure.
- Where a concrete workspace promotion contract is implemented, verify its validation, required Operation, and snapshot policy as part of the lifecycle.

## Out of Scope

- Defining a workspace dataset's unresolved Review editing or promotion mapping rules.
- New workspace dataset types, UI behavior, or import workflow changes.
- Treating generic lifecycle rules as authorization to invent a permanent-entity promotion policy.

## Dependencies

- `BT-018` — provides isolated workflow fixtures and runner conventions.
- `BT-007`, `BT-011`, and `BT-012` — provide workspace lifecycle, snapshot, and Operation behavior under test.
- A resolved dataset-specific Review editing and promotion contract when the tested workspace supports promotion.

## Implementation Steps

1. Identify the implemented workspace dataset and its resolved state-specific editing contract.
2. Add lifecycle scenarios covering each specified valid transition and representative prohibited action.
3. Add promotion assertions only for a dataset with an explicit resolved promotion contract.
4. Assert persistence and zero side effects after rejected actions.

## Acceptance Criteria

- Valid lifecycle transitions persist the specified resulting state and historical traceability.
- Invalid transitions and prohibited edits are rejected without modifying workspace or production state.
- Closed and Archived / Retired workspaces are excluded from normal business editing and processing.
- Any implemented promotion validates before permanent writes and creates required Operation and snapshot evidence.

## Verification

- Run focused workspace lifecycle workflow scenarios with a disposable database.
- Run workspace, snapshots, and operations regression groups, then the complete suite.

## Risks or Notes

- Promotion remains blocked for any workspace dataset whose field-level review and promotion contract is not yet resolved in its Specification.
