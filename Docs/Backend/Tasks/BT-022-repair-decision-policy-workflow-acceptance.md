# BT-022 — Verify Repair Decision Policy Workflows

## Task ID

`BT-022` — Status: `Blocked`

## Title

Verify Repair Decision Policy Workflows

## Related Specification(s)

- [Repair Workflow](../Specifications/Repair-Workflow.md), Normative automatic-correction policy, Normative fuzzy path-match evidence, Normative quarantine policy, and Snapshot requirements sections.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), path comparison and collision requirements.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), required snapshot policy.
- [Authentication](../Specifications/Authentication.md), authorization model.

## Goal

Verify that repair classification and execution enforce the specified safety boundaries for automatic, assisted, manual-conflict, ignored, and quarantine-related decisions.

## Scope

- Test an eligible canonicalization-only automatic rename and a near-identical but ineligible path change.
- Test assisted repair confirmation, ambiguous candidates entering or remaining in `ManualConflict`, and failed verification returning to an unresolved state.
- Test `Ignored` rediscovery and the bounded, auditable behavior of an active or expired suppression record where implemented.
- Test quarantine and restore safety, role restrictions, and required pre-action snapshot decisions for destructive or multi-directory actions.

## Out of Scope

- General import failure hand-off already covered by `BT-020`.
- New fuzzy-matching heuristics, retention policies, or UI interaction design.
- Permanently deleting quarantined data outside the currently implemented retention workflow.

## Dependencies

- `BT-018` — provides isolated filesystem, quarantine, and snapshot fixtures.
- `BT-010`, `BT-011`, `BT-012`, `BT-013`, `BT-014`, and `BT-015` — provide the repair, snapshot, authorization, path, operation, and Issue boundaries under test.

## Implementation Steps

1. Build deterministic managed-directory fixtures for each repair decision category.
2. Add workflow scenarios that select and execute only permitted repair actions.
3. Assert required confirmation, snapshots, authorization, state transitions, and preserved filesystem contents.
4. Add rediscovery and failed-verification scenarios to the workflow-test group.

## Acceptance Criteria

- Only the complete automatic-correction policy permits an unconfirmed automatic rename.
- Ineligible or ambiguous conditions cannot be silently repaired and remain assisted or `ManualConflict` as specified.
- `Resolved` is reached only after required consistency verification succeeds.
- Ignoring a case does not assert consistency and does not suppress later discovery without a separate active suppression record.
- Quarantine, restoration, and destructive repair actions preserve data safety, authorization, audit evidence, and required snapshot protection.

## Verification

- Run focused repair-decision workflow scenarios against disposable managed and quarantine roots.
- Run repair, canonical-path, authentication, snapshots, and operations regression groups, then the complete suite.

## Risks or Notes

- Blocked by the absence of a policy-enforcing repair execution boundary: the current `RepairService` persists only generic state transitions. It cannot classify or execute canonicalization-only renames, preserve fuzzy-match evidence, persist suppression records, or run quarantine and restore actions. These are tracked by `BT-028` and `BT-029`; this acceptance task must resume after them rather than weakening its scenarios.
