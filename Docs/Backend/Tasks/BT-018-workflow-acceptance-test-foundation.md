# BT-018 — Establish Workflow Acceptance Test Foundation

## Task ID

`BT-018` — Status: `Complete`

## Title

Establish Workflow Acceptance Test Foundation

## Related Specification(s)

- [Testing Strategy](../Testing-Strategy.md), Workflow Tests, Sandbox Environment, and Mock File System sections.
- [Backend Specifications](../Specifications/README.md), shared conventions.
- [Operation Logging](../Specifications/Operation-Logging.md), required record content section.

## Goal

Create a repeatable, UI-independent acceptance-test foundation for complete Backend business workflows. The foundation must exercise real service and repository collaboration against disposable database and filesystem resources.

## Scope

- Provide shared fixtures for an isolated SQLite database and disposable source, archive, snapshot, and quarantine filesystem roots.
- Provide scenario builders and assertions for production records, filesystem effects, Operations, Issues, snapshots, and repair linkage.
- Add a named workflow-test runner or group that is separate from focused unit and service tests.
- Ensure failure output identifies the scenario and controlling Specification boundary.

## Out of Scope

- Starting or automating the Web UI.
- Changing production behavior, database schema, or Specification rules merely to accommodate tests.
- Load, performance, browser, or production-environment testing.

## Dependencies

- `BT-017` — provides the existing isolated regression-suite conventions and entry point.
- [Testing Strategy](../Testing-Strategy.md) — controls isolation, repeatability, and resource safety.

## Implementation Steps

1. Inventory existing service and regression fixtures that can be reused without coupling workflow scenarios to implementation details.
2. Add disposable workflow sandbox builders and explicit production-path guards.
3. Add shared observable-state assertions and a focused workflow-test runner/group.
4. Demonstrate repeatability by running a representative scenario twice from clean fixtures.

## Acceptance Criteria

- A workflow test can create all required database and filesystem state without reading or modifying production resources.
- Each scenario can assert durable database records, filesystem results, and cross-record identifiers without relying on log ordering or private service internals.
- The workflow test group is independently runnable and gives scenario-level failure names.
- Repeating the same scenario begins from a clean state and produces equivalent results.

## Verification

- Run the workflow-test group twice with fresh disposable resources.
- Run the complete Backend regression suite to confirm the new fixtures do not affect focused tests.
- Verify a deliberately invalid fixture reports the named scenario and Specification boundary.

## Risks or Notes

- Tests must use real temporary filesystem operations where their outcome is part of the workflow; use narrow failure injection only for conditions that cannot be made deterministic otherwise.
