# BT-020 — Verify Import Failure and Repair Recovery Workflow

## Task ID

`BT-020` — Status: `Complete`

## Title

Verify Import Failure and Repair Recovery Workflow

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), Error handling and repair and Operation and snapshot requirements.
- [Repair Workflow](../Specifications/Repair-Workflow.md), repair state machine and Validation rules sections.
- [Issue Management](../Specifications/Issue-Management.md), workflow linkage requirements.
- [Operation Logging](../Specifications/Operation-Logging.md), lifecycle requirements and Operations and Issues section.

## Goal

Verify the recoverable failure path in which import persistence succeeds but required filesystem work fails, and prove that subsequent repair and verification preserve a truthful, linked history.

## Scope

- Inject a deterministic post-persistence filesystem failure for `COPY` or `MOVE`.
- Verify the resulting persisted import context, `NeedsRepair` Operation, Repair case, and related Issue where persistent review is required.
- Exercise a permitted repair action and successful verification through `Resolved`.
- Assert the original failed Operation remains historical evidence and the repair is recorded as linked subsequent activity.

## Out of Scope

- The full automatic, assisted, quarantine, and suppression policy matrix; those belong to `BT-022`.
- Automatic rollback that deletes persisted business data after a post-persistence filesystem failure.
- Web UI confirmation flows.

## Dependencies

- `BT-019` — establishes the supported successful import workflow and fixtures.
- `BT-010`, `BT-012`, and `BT-015` — provide Repair, Operation, and Issue behavior under test.

## Implementation Steps

1. Add a deterministic failure-injection point after production persistence and before a verified filesystem outcome.
2. Create an import-to-repair scenario using the public service boundaries.
3. Complete a permitted repair and verification action in the same isolated sandbox.
4. Assert final filesystem consistency and the complete immutable Operation/Repair/Issue linkage.

## Acceptance Criteria

- A filesystem failure after persistence is never reported as a successful import and does not erase the persisted recovery context.
- The original import Operation is `NeedsRepair` and carries stable failure and repair context.
- The repair flow can reach `Resolved` only after consistency verification succeeds.
- The original failed Operation is not rewritten to `Succeeded`; repair and verification records identify their relationship to it.
- The resulting filesystem state agrees with the canonical database path without overwriting unrelated data.

## Verification

- Run the focused import-recovery workflow scenario with deterministic filesystem failure injection.
- Run focused repair, issue, and operations regression groups, followed by the complete suite.

## Risks or Notes

- Keep failure injection at the adapter boundary so the scenario tests workflow behavior rather than mock call order.
