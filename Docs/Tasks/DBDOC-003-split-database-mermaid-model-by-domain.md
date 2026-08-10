# DBDOC-003 — Split Database Mermaid Model by Domain

## Task ID

`DBDOC-003` — Status: `Complete`

## Goal

Replace the outdated single database diagram with a navigable overview and
bounded domain diagrams that accurately represent the current schema.

## Scope

- Create a system-level domain relationship overview.
- Create Mermaid ER diagrams for Asset Catalog, Authentication,
  Operations/Repair/Recovery, Work Dispatch, and AI Workspace.
- Split AI execution/evidence and review/promotion further if one diagram is
  not readable at normal documentation width.
- Mark polymorphic, Service-enforced, historical, and claim relationships
  explicitly in accompanying prose where Mermaid cannot express them accurately.

## Out of Scope

- Treating conceptual relationships as physical foreign keys.
- Adding schema solely to make diagrams more symmetrical.

## Inputs and Authority

- DBDOC-002 Schema Catalog.
- Current migrations and controlling Backend Specifications.

## Deliverables

- `Docs/Database/Diagrams/00-System-Overview.md`.
- `01-Asset-Catalog.md`, `02-Authentication.md`,
  `03-Operations-Repair-Recovery.md`, `04-Work-Dispatch.md`, and
  `05-AI-Workspace.md`.
- A rewritten `Curator_Database_Model.md` serving as the diagram index.

## Acceptance Criteria

- Every cataloged domain is represented without producing one unreadable mega-diagram.
- Table and relationship names match the current schema exactly.
- Active exclusive reservation, retained history, staged AI results, review,
  rework, and unique Promotion are understandable from diagrams plus notes.
- Historical `workspace_album` is excluded from active diagrams and linked as history.

## Verification

- Render every Mermaid block successfully.
- Cross-check all diagram entities and FK edges with DBDOC-002.

## Dependencies

- DBDOC-002.

## Risks or Notes

- Mermaid ER syntax cannot express partial unique indexes or all polymorphic
  links; those rules must be stated accurately rather than implied by a false edge.

## Completion Record

- Replaced the obsolete single v0.2 diagram with a current diagram index.
- Added a domain overview plus Asset, Authentication, Operations/Recovery,
  Dispatch, and split AI Workspace ER models.
- Documented logical/polymorphic edges, Service rules, partial unique indexes,
  claims, active reservations, retained history, and historical exclusion.
