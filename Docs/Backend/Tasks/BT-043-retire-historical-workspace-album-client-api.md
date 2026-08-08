# BT-043 — Retire Historical Workspace Album Client API

## Task ID

`BT-043` — Status: `Proposed`

## Title

Retire Historical Workspace Album API from Active Client Access

## Related Specification(s)

- [Workspace Workflow](../Specifications/Workspace-Workflow.md), historical retention direction.
- UI-011A AI Collection Workspace Specification, once approved.

## Goal

Prevent the archived `workspace_album` collection from being read or mutated as
active Workspace input while preserving explicitly authorized historical audit access.

## Scope

- Remove ordinary Reader/Writer access to legacy Workspace Album routes.
- Reject all legacy create, update, batch, transition, and promotion attempts.
- If historical inspection remains required, expose a separately named,
  Admin-only, read-only history contract with redacted safe read models.
- Ensure the AI Worker cannot discover or consume historical records.

## Out of Scope

- Deleting historical Workspace records.
- Reusing `workspace_album` for the new AI Dataset.

## Dependencies

- MT-008 historical archival completion.
- UI-011A decision on whether an Admin history surface remains necessary.

## Implementation Steps

1. Inventory all legacy Workspace Album routes, services, callers, and tests.
2. Close active-client routes and optionally add the Admin history namespace.
3. Add authorization, no-mutation, AI Worker isolation, and compatibility tests.

## Acceptance Criteria

- Reader and Writer Tokens cannot list or retrieve historical Workspace Albums.
- No supported API can return an archived row to Active or Review.
- AI Worker workflow and fixtures contain no legacy Workspace input.
- Historical evidence remains intact and traceable when Admin audit access is retained.

## Verification

- Versioned API authorization and historical read-only tests.
- AI Worker negative-access tests and complete Backend regression.

## Risks or Notes

- Status and entity reference-count behavior may still depend on the archived
  table internally; retiring the client API must not break referential checks.
