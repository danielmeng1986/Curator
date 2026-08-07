# BT-019 — Verify Import Happy-Path Workflows

## Task ID

`BT-019` — Status: `Proposed`

## Title

Verify Import Happy-Path Workflows

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), staged workflow, Album preview and confirmation, and Import Action sections.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), normalization and collision requirements.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), risk-based snapshot decision requirements.
- [Operation Logging](../Specifications/Operation-Logging.md), import execution requirements.

## Goal

Verify that a confirmed Album import completes as one coherent Backend workflow for the supported `DATABASE_ONLY`, `COPY`, and `MOVE` actions, leaving the specified durable business and operational outcomes.

## Scope

- Add end-to-end service-level scenarios from preview through identity confirmation, persistence, optional filesystem action, snapshot decision, and successful Operation outcome.
- Cover a new Album, a valid canonical destination, and the policy that selects `DATABASE_ONLY` when the source is already at its canonical destination.
- Assert production entities, canonical paths, source/destination filesystem state, selected action, and Operation context.

## Out of Scope

- Filesystem failure and Repair hand-off scenarios; those belong to `BT-020`.
- Semantic duplicate merge or Photo import, which are outside the current Import Workflow scope.
- Web UI automation.

## Dependencies

- `BT-018` — provides isolated workflow fixtures and runner conventions.
- `BT-008`, `BT-009`, `BT-011`, `BT-012`, and `BT-014` — provide the implemented import, snapshot, operation, and path boundaries under test.

## Implementation Steps

1. Define deterministic source-directory fixtures and confirmed Album identities for each supported Import Action.
2. Add scenarios that invoke the public service workflow and inspect only specified observable outcomes.
3. Assert database persistence, canonical-path safety, filesystem result, snapshot decision where applicable, and successful Operation record.
4. Add the scenarios to the workflow-test group.

## Acceptance Criteria

- Preview alone produces no production persistence, snapshot, or production import Operation.
- A confirmed valid import persists the specified production identity before any required filesystem stage.
- `DATABASE_ONLY`, `COPY`, and `MOVE` have their specified and distinguishable filesystem outcomes.
- Each successful execution has a durable `Succeeded` Operation with its import context and selected action.
- A source already at its canonical destination performs no redundant filesystem action.

## Verification

- Run the focused import happy-path workflow scenarios against disposable database and filesystem roots.
- Run the import and snapshot regression groups, then the complete suite.

## Risks or Notes

- A failing acceptance scenario is evidence of an implementation or Specification gap; do not weaken its assertions to match incidental current behavior.
