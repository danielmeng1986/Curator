# BT-044 — Establish AI Workspace Container and Dataset Schema Contract

## Task ID

`BT-044` — Status: `Proposed`

## Title

Establish AI Workspace Container and Album-Analysis Dataset Schema

## Related Specification(s)

- UI-011A AI Collection Workspace Specification.
- UI-011B stable Workspace review state machine.
- [Workspace Workflow](../Specifications/Workspace-Workflow.md).

## Goal

Create a versioned AI Workspace container and the first `album_analysis`
Dataset boundary without coupling it to historical `workspace_album` storage.

## Scope

- Versioned `ai_workspace` identity, Dataset type, ownership, timestamps, and version.
- Container lifecycle `Open → Closed → Archived` with read-only terminal behavior.
- Dataset schema registry/version and stable relationship to Album-analysis Items.
- Migration, repository, service, safe queue metadata, and Operation evidence.

## Out of Scope

- Model execution, Photo transfer, review decisions, and Album Promotion.
- A generic user-defined Dataset language.

## Dependencies

- Approved UI-011A and UI-011B Specifications.
- BT-043 namespace and historical-data isolation decision.

## Implementation Steps

1. Add versioned schema migrations and normalized repository models.
2. Implement container lifecycle services and Admin management APIs.
3. Add lifecycle, versioning, authorization, archive, and migration tests.

## Acceptance Criteria

- New records use a Dataset type and schema version understood by the Backend.
- Closed Workspaces accept no new Items; Archived Workspaces are fully read-only.
- Container state never substitutes for Item run/review/promotion state.
- No new table or API reads from historical `workspace_album`.

## Verification

- Migration/repository tests, lifecycle service tests, API contract tests, and full regression.

## Risks or Notes

- Schema evolution must preserve stable review fields and evidence even when
  Dataset-specific JSON changes.
