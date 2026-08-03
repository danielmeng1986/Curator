# BT-010 — Implement the Repair Workflow State Machine

## Task ID

`BT-010` — Status: `Ready`

## Title

Implement the Repair Workflow State Machine

## Related Specification(s)

- [Repair Workflow](../Specifications/Repair-Workflow.md), detection, states, confirmation, execution, and verification sections.
- [Issue Management](../Specifications/Issue-Management.md), repair-issue linkage and lifecycle requirements.
- [Repository Specification](../Specifications/Repository-Specification.md), repair and issue persistence contracts.

## Goal

Implement the specified Repair Workflow as a persistent state machine that detects issues, enforces valid transitions, records confirmation, and verifies completed repairs.

## Scope

- Detect and persist specified repair issues.
- Define and enforce the specified repair state transitions in service logic.
- Handle required user confirmation before repair actions.
- Persist each meaningful workflow step and post-repair verification outcome.
- Add full lifecycle workflow tests.

## Out of Scope

- Changing repair states, transition rules, confirmation requirements, or verification criteria.
- Implementing unrelated import execution, snapshot, or authentication workflows.
- Adding UI features beyond the existing service and API integration points.

## Dependencies

- `BT-005` — repair and issue persistence must be accessed through repositories.
- [Repair Workflow](../Specifications/Repair-Workflow.md) — controls state-machine behavior and recovery expectations.
- [Issue Management](../Specifications/Issue-Management.md) — controls persistent issue linkage where required.

## Implementation Steps

1. Map specified repair detection outcomes, states, allowed transitions, and confirmation requirements.
2. Add repository operations to persist repair issues, state changes, confirmations, and verification outcomes.
3. Implement repair service operations that reject invalid transitions and coordinate valid lifecycle steps.
4. Add tests that cover detection through post-repair verification, including invalid transitions.

## Acceptance Criteria

- Specified repair issues are detected and recorded through the normal persistence path.
- Only valid Repair Workflow transitions are accepted; invalid transitions leave persisted state unchanged.
- Required user confirmation is recorded and enforced before the associated repair action.
- Post-repair verification is persisted and determines the specified terminal workflow outcome.
- Automated tests cover the full repair lifecycle and invalid-transition cases.

## Verification

- Run focused repair-service state-machine tests for each valid and invalid transition.
- Run repository tests for persisted repair steps, confirmations, and verification results.
- Run applicable issue-management and workflow regression tests.

## Risks or Notes

- Treat unresolved repair-state semantics as a Specification decision before implementing persistence or transition logic.
- Preserve sufficient repair history to diagnose and resume a partially completed workflow.
