# DOC-001 — Establish Documentation Authority and Lifecycle

## Task ID

`DOC-001` — Status: `Proposed`

## Goal

Define which Curator documents are authoritative for intent, architecture,
contracts, implementation status, and history so humans and AI Agents can
resolve apparent conflicts without guessing.

## Scope

- Define document classes: `Current`, `Approved`, `Historical`, `Memo`, and `Task`.
- Define precedence among code/schema, Specifications, Architecture, Tasks,
  conceptual documents, and historical records.
- Define required status metadata, ownership, review triggers, and archival rules.
- Define when a change must update documentation and when it must create a BT,
  UI, MT, DOC, or DBDOC task instead.

## Out of Scope

- Rewriting every existing document.
- Changing application behavior or database structure.

## Inputs and Authority

- `Docs/README.md`, `Docs/AI-CONTEXT.md`.
- Backend, UI, Project, and new Documentation task conventions.
- Current implementation and accepted Specifications.

## Deliverables

- `Docs/Documentation-Governance.md`.
- A concise authority and lifecycle summary linked from `Docs/README.md`.
- A reusable document-status header convention.

## Acceptance Criteria

- A reader can determine whether a document describes current truth, an
  approved target, history, a non-binding idea, or unfinished work.
- Conflict precedence is explicit and does not imply that stale docs override code.
- Historical documents remain discoverable but cannot be mistaken for active guidance.
- Task ownership rules prevent documentation tasks from silently changing runtime contracts.

## Verification

- Classify a representative Backend Specification, UI task, migration guide,
  architecture document, and memo using the new rules.
- Verify every new link from the documentation index resolves.

## Dependencies

- None.

## Risks or Notes

- Governance should remain lightweight; metadata must improve decisions without
  turning ordinary documentation edits into a bureaucratic workflow.

