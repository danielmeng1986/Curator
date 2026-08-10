# DBDOC-002 — Build Current Database Schema Catalog

## Task ID

`DBDOC-002` — Status: `Complete`

## Goal

Create a complete, concise, machine-scannable catalog of the current Curator
database so an AI Agent can locate tables, ownership, relationships, and
lifecycle semantics without searching Repository implementation code.

## Scope

- Catalog every table, primary key, business identity, important foreign key,
  unique/check constraint, and significant index.
- Assign each table to a domain and persistence role.
- Classify tables as active state, exclusive reservation, immutable history,
  audit, ephemeral preview/claim, configuration, or historical/archived.
- Link each entry to its authoritative schema source and controlling Specification.

## Out of Scope

- Reproducing every SQL statement verbatim.
- Changing table names, constraints, or indexes.

## Inputs and Authority

- DBDOC-001 schema-source inventory.
- Applied migrations, Repository schema definitions, and Specifications.

## Deliverables

- `Docs/Database/Schema-Catalog.md`.
- A domain/table index used by the Mermaid and workflow documents.

## Acceptance Criteria

- All active, historical, claim, audit, and migration bookkeeping tables appear.
- Each table has domain, purpose, lifecycle, owner, main relationships, and source.
- `workspace_album` is explicitly historical and cannot be confused with
  `workspace_album_ai_worker`.
- Service-only constraints such as last-Admin safety are distinguished from DB constraints.

## Verification

- Compare catalog table names with an initialized disposable database and all
  authoritative schema sources.
- Check all catalog links and controlling Specification references.

## Dependencies

- DOC-001.
- DBDOC-001.

## Risks or Notes

- Catalog brevity matters: details should support navigation, while exact SQL
  remains in the authoritative schema source.

## Completion Record

- Added `Docs/Database/Schema-Catalog.md` covering all active, historical,
  configuration, reservation, claim, history, audit, and bookkeeping tables.
- Recorded identity, lifecycle role, important relationships/constraints,
  authoritative source, and controlling contract for each table.
- Explicitly separated database constraints from Service-enforced safety rules.
