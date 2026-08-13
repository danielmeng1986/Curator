# UI-001 — Establish UI Workflow Coverage Matrix

## Task ID

`UI-001` — Status: `Complete`

## Title

Establish UI Workflow Coverage Matrix

## Related Specification(s)

- [UI documentation index](../README.md) and its foundation, interaction,
  feature, and verification documents.
- [Backend Workflow Readiness Matrix](../../Backend/Workflow-Readiness-Matrix.md).
- [Authentication](../../Backend/Specifications/Authentication.md), [Import](../../Backend/Specifications/Import-Workflow.md), [Repair](../../Backend/Specifications/Repair-Workflow.md), and [Workspace](../../Backend/Specifications/Workspace-Workflow.md).

## Goal

Create the controlling map from every supported Backend workflow to its UI
surface, user role, browser evidence, or explicit exclusion/blocker.

## Scope

- Classify each workflow as full UI operation, UI result visibility,
  administrator-only operation, intentionally non-UI, or specification-blocked.
- Replace stale UI assumptions about authentication and the retired historical
  `workspace_album` surface.
- Include placeholders for the future AI Collection Workspace without exposing
  archived historical Workspace data.

## Out of Scope

- Implementing pages, APIs, or browser scenarios.
- Defining the dataset-specific AI Workspace schema.

## Dependencies

- Current Backend workflow matrix and completed Backend acceptance evidence.
- Product decisions recorded in UI-004B and UI-011A before those rows can be Ready.

## Implementation Steps

1. Inventory supported routes, workflows, roles, material mutations, and Backend tests.
2. Amend UI modules 01–06 so their scope agrees with current Architecture and decisions.
3. Publish a matrix with UI route, role, happy path, rejection path, durable evidence, test owner, and readiness classification.

## Acceptance Criteria

- Every Ready Backend workflow has a mapped UI outcome or an explicit approved exclusion.
- Historical Workspace routes are not presented as active UI requirements.
- Authentication, administration, and future AI Workspace rows expose their specification dependencies.
- Classifications use `Ready`, `Failing`, `Not Implemented`, or `Blocked by Specification` consistently.

## Verification

- Cross-review the matrix against Backend workflow-readiness test names and active `/api/v1` routes.
- Verify every UI-004 through UI-015 task maps back to at least one matrix row.

## Risks or Notes

- This matrix controls coverage but does not replace the controlling workflow Specifications.

## Completion Record

- Published the initial UI Workflow Readiness Matrix with Backend evidence,
  user role, route, browser owner, rejection evidence, and readiness gap for
  every currently Ready Backend workflow and planned AI Workspace outcome.
- Amended UI modules 01–06 to remove the active historical `workspace_album`
  assumption and bring approved-device authentication, roles, Operation
  history, administration, and the future Workspace specification boundary into
  the UI plan.
- Confirmed that the existing browser test remains smoke evidence only; it does
  not silently make incomplete feature rows Ready.
