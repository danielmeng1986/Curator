# BT-031 — Resolve Workspace Review and Promotion Contract

## Task ID

`BT-031` — Status: `Blocked`

## Title

Resolve Workspace Review and Promotion Contract

## Related Specification(s)

- [Workspace Workflow](../Specifications/Workspace-Workflow.md), Controlled Review Modifications and promotion requirements.

## Goal

Resolve the dataset-specific Review fields, validation, and permanent-entity promotion mapping required before promotion can be implemented or accepted.

## Scope

- Specify permitted Review edits and immutable fields.
- Specify promotion validation, entity mapping, Operation and snapshot requirements.

## Out of Scope

- Implementing promotion before the Specification decision is approved.

## Dependencies

- A Specification decision by the product/architecture owner.

## Implementation Steps

1. Decide the workspace dataset and field-level Review contract.
2. Define promotion mapping and failure/recovery rules in the Specification.
3. Create a separately scoped implementation and acceptance task after approval.

## Acceptance Criteria

- The controlling Specification unambiguously defines permitted Review edits and promotion behavior.

## Verification

- Review the amended Specification before implementation work begins.

## Risks or Notes

- This task is intentionally blocked: generic lifecycle rules do not authorize inventing a permanent promotion policy.
