# DBDOC-004 — Document Persistence Workflow Boundaries

## Task ID

`DBDOC-004` — Status: `Complete`

## Goal

Explain how important workflows move through current-state, claim, audit, and
history tables so readers can reason about transactions and recovery without
reverse-engineering individual Repository methods.

## Scope

- Document Album Import preview and execution persistence.
- Document Issue, Repair, Quarantine, Snapshot, and Restore persistence.
- Document Album-exclusive Work Dispatch, closure, release, and redispatch.
- Document AI evidence, two-stage result submission, review, rework, Promotion,
  Workspace closure, archive, and retention.
- Identify transaction boundaries, durable zero-write rejection expectations,
  and links to Operation records.

## Out of Scope

- Restating the full HTTP API.
- Inventing transaction guarantees absent from the implementation or Specification.

## Inputs and Authority

- DBDOC-002 and DBDOC-003.
- Backend workflow Specifications and workflow-readiness tests.

## Deliverables

- `Docs/Database/Workflows/Album-Import-Persistence.md`.
- `Repair-and-Quarantine-Persistence.md`.
- `Work-Dispatch-Persistence.md`.
- `AI-Review-and-Promotion-Persistence.md`.

## Acceptance Criteria

- Each workflow identifies participating tables and their persistence roles.
- Preview/claim records are distinguished from business outcomes and audit history.
- Failure, cancellation, replay, release, and archive outcomes are described truthfully.
- Readers can identify what is deleted, retained, updated, or immutable at each transition.

## Verification

- Trace each documented happy and rejection path to a Backend workflow test.
- Verify table names and state values against Schema Catalog and Specifications.

## Dependencies

- DBDOC-002.
- DBDOC-003.

## Risks or Notes

- These documents explain persistence, not product UI steps; UI behavior remains
  controlled by UI Specifications and tasks.

## Completion Record

- Added four persistence maps covering Import, Repair/Quarantine, Dispatch, and
  AI execution/review/Promotion.
- Each map distinguishes preview/claim, current projection, immutable history,
  audit, filesystem artifact, rejection, and retention behavior.
- Linked every workflow to controlling Specifications and acceptance evidence.
