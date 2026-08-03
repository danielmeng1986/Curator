# BT-007 — Implement the Workspace Lifecycle Workflow

## Task ID

`BT-007` — Status: `Ready`

## Title

Implement the Workspace Lifecycle Workflow

## Related Specification(s)

- [Workspace Workflow](../Specifications/Workspace-Workflow.md), lifecycle, promotion, cleanup, and invalid-state sections.
- [Repository Specification](../Specifications/Repository-Specification.md), workspace persistence contracts.
- [Backend Architecture](../Backend-Architecture.md), Workspace Lifecycle and Domain Service Layer sections.

## Goal

Implement the specified Workspace lifecycle through service and repository boundaries, including creation, valid state transitions, promotion, and retirement handling.

## Scope

- Add workspace creation and lifecycle-state persistence through repository methods.
- Implement specified state transitions, promotion behavior, and cleanup or retirement handling in service logic.
- Reject invalid lifecycle operations before persistence changes.
- Add focused state-transition and persistence tests.

## Out of Scope

- Changing the Workspace lifecycle states, transition rules, or promotion criteria defined by the specification.
- Adding new workspace types, UI features, or unrelated import and repair workflows.
- Implementing HTTP transport changes beyond exposing existing service operations.

## Dependencies

- `BT-005` — workspace persistence must be accessed through repository modules.
- `BT-006` — workspace repository outputs must use canonical read models where consumed by services.
- [Workspace Workflow](../Specifications/Workspace-Workflow.md) — controls allowed states, transitions, promotion, and retirement behavior.

## Implementation Steps

1. Map the specified lifecycle states, allowed transitions, promotion conditions, and retirement rules to service operations.
2. Add repository methods to create, retrieve, and persist workspace lifecycle state.
3. Implement lifecycle validation and workflow operations in the workspace service.
4. Add tests for creation, valid transitions, invalid-state rejection, promotion, and retirement handling.

## Acceptance Criteria

- Workspaces are created and persisted with the specified initial lifecycle state.
- Only specified transitions and promotion operations are accepted by service logic.
- Invalid-state operations are rejected without changing persisted workspace state.
- Cleanup or retirement behavior follows the Workspace Workflow specification and is persisted consistently.
- Automated state-transition tests cover the complete specified lifecycle.

## Verification

- Run focused service tests for each valid and invalid lifecycle transition.
- Run repository tests for workspace creation and state persistence.
- Run applicable workflow and API regression tests to confirm existing workspace behavior remains stable.

## Risks or Notes

- Treat the Workspace Workflow specification as authoritative; unresolved transition details must be resolved there before implementation.
- Preserve workspace history and audit requirements when applying promotion or retirement operations.
