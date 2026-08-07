# BT-031 — Resolve Workspace Review and Promotion Contract

## Task ID

`BT-031` — Status: `Complete`

## Title

Resolve Workspace Review and Promotion Contract

## Related Specification(s)

- [Workspace Workflow](../Specifications/Workspace-Workflow.md), Controlled Review Modifications and `workspace_album` Review and promotion contract.
- [Curator Domain Model](../../Database/Curator_Domain_Model.md), Workspace-to-Album migration semantics.

## Goal

Resolve the dataset-specific Review fields, validation, and permanent-entity promotion mapping required before promotion can be implemented or accepted.

## Scope

- Specified permitted Review edits, final-selection freeze at `Approved`, and immutable/system-managed fields.
- Specified promotion validation, two-phase permanent-entity mapping, Operation, snapshot, and recovery requirements.
- Defined `workspace_album` as a historical collection to be closed and archived, while retaining the contract for future dataset-specific Workspaces.

## Out of Scope

- Implementing promotion before the Specification decision is approved.

## Dependencies

- Resolved by the product/architecture owner on 2026-08-08.

## Implementation Steps

1. Decide the workspace dataset and field-level Review contract. — Complete
2. Define promotion mapping and failure/recovery rules in the Specification. — Complete
3. Create separately scoped database-compatibility and historical-workspace migration tasks. — Complete

## Acceptance Criteria

- The controlling Specification unambiguously defines permitted Review edits, final selection, promotion behavior, and failure handling.
- Follow-on tasks isolate permanent-schema compatibility from historical Workspace closure.

## Verification

- Reviewed the amended Specification and linked database models before implementation work begins.

## Risks or Notes

- `album.remark` requires a separately versioned database migration and compatibility task.
- Promotion and archival of historical `workspace_album` data require a separately recoverable migration task.
