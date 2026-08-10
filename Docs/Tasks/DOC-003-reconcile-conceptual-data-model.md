# DOC-003 — Reconcile Conceptual Data Model

## Task ID

`DOC-003` — Status: `Proposed`

## Goal

Align Curator's conceptual data model with implemented domains while clearly
separating current capabilities, approved near-term design, and future ideas.

## Scope

- Reconcile `Docs/04-Data-Model.md` and
  `Docs/Database/Curator_Domain_Model.md`.
- Define Album as the current apps.web management unit and Photo as an asset and
  evidence entity rather than the primary Web management surface.
- Describe Album Status independently from Work Dispatch execution/review state.
- Describe AI Workspace, Work Item, evidence, review, rework, and Promotion concepts.
- Classify unimplemented Asset, Annotation, Rename Plan, embeddings, and native
  curation concepts as future where appropriate.

## Out of Scope

- Physical table-by-table documentation.
- Final design of the macOS native Curator application.

## Inputs and Authority

- Current Database Domain Model and DBDOC outputs.
- Approved Backend and UI Specifications.
- `Docs/Project/macOS-Native-Curator-Memo.md` as non-binding future context.

## Deliverables

- Updated conceptual `Docs/04-Data-Model.md`.
- Updated `Docs/Database/Curator_Domain_Model.md`.
- Explicit Current / Approved / Future labels for major concepts.

## Acceptance Criteria

- Conceptual entities do not imply unimplemented tables or UI capabilities.
- Historical Workspace and current AI Workspace are clearly distinct.
- Album, Photo, Dispatch, Worker, Review, and Promotion boundaries match approved behavior.
- Future native curation remains discoverable without becoming a current contract.

## Verification

- Cross-check current concepts against Schema Catalog and workflow Specifications.
- Search for conflicting active definitions of Workspace, Asset, and Photo ownership.

## Dependencies

- DOC-002.
- DBDOC-002 through DBDOC-005.

## Risks or Notes

- Conceptual models should remain storage-independent, but must not contradict
  the capabilities and boundaries of the current system.

