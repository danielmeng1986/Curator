# BT-009 — Implement Import Filesystem Execution

## Task ID

`BT-009` — Status: `Ready`

## Title

Implement Import Filesystem Execution

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), execution, persistence, failure, and recovery sections.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), final-path derivation and collision rules.
- [Operation Logging](../Specifications/Operation-Logging.md), material-write recording requirements.

## Goal

Execute validated imports through coordinated filesystem and persistence operations, with specified compensation and durable recording of successful or partial outcomes.

## Scope

- Execute specified copy or move operations only after successful import validation.
- Coordinate filesystem execution with repository-backed database writes.
- Implement specified failure detection, compensation, and recovery visibility for partial failures.
- Persist the final import outcome through the normal backend persistence path.
- Add focused success and failure-path tests.

## Out of Scope

- Generating previews, duplicate detection, or pre-write collision validation.
- Changing specified import, path, copy, move, or recovery behavior.
- Building unrelated repair, snapshot, or UI workflows beyond required integration points.

## Dependencies

- `BT-008` — execution requires a successful deterministic preview and validation decision.
- `BT-005` — database writes and outcome persistence must use repositories.
- [Import Workflow](../Specifications/Import-Workflow.md) — controls execution order, compensation, and recovery behavior.

## Implementation Steps

1. Define the execution command from a validated import result and the specified copy or move mode.
2. Implement coordinated repository and filesystem operations with explicit failure boundaries.
3. Implement specified compensation and persistent recovery information for partial failures.
4. Persist final outcomes and add tests for success, filesystem failure, persistence failure, and compensation paths.

## Acceptance Criteria

- Filesystem operations run only after a successful validation decision and use specified final paths.
- Database writes and filesystem changes are coordinated according to the Import Workflow specification.
- Partial failures are persisted, visible, and recoverable through the specified compensation behavior.
- Final successful and failed outcomes are recorded through backend persistence.
- Automated tests cover copy or move execution and representative partial-failure recovery cases.

## Verification

- Run focused import workflow tests using isolated filesystem and database fixtures.
- Inject filesystem and persistence failures to verify compensation and durable recovery state.
- Run applicable operation-recording and import regression tests.

## Risks or Notes

- Filesystem and database actions cannot share a single atomic transaction; compensation and outcome recording must make their combined state understandable.
- Do not re-run validation rules during execution in a way that changes the approved import decision without reporting a new validation result.
