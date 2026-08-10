# DBDOC-001 — Establish Database Schema Source of Truth

## Task ID

`DBDOC-001` — Status: `Proposed`

## Goal

Document and, where necessary, reconcile the authority of base schema,
versioned migrations, Repository compatibility DDL, and test fixtures so the
current Curator database can be reconstructed and understood deterministically.

## Scope

- Inventory schema definitions in migrations, repositories, and test fixtures.
- Identify the authoritative source for every active and historical table.
- Explain empty-database creation, migration ordering, compatibility schema
  checks, and `schema_migration` bookkeeping.
- Record discrepancies as explicit BT or DBDOC follow-ups; do not resolve
  runtime behavior silently.

## Out of Scope

- Moving DDL or changing migration execution behavior.
- Modifying production or local runtime databases.

## Inputs and Authority

- `apps/backend/migrations/` and its runner.
- Schema-creating code in `apps/backend/repositories.py`.
- Backend schema fixtures and migration tests.
- Backend Repository and Snapshot Specifications.

## Deliverables

- `Docs/Database/Schema-Source-of-Truth.md`.
- A table-to-authoritative-source inventory suitable as input to DBDOC-002.
- A documented rule for future table and column additions.

## Acceptance Criteria

- Every persisted table has one declared authoritative definition.
- The roles of migrations, Repository defensive DDL, and test fixtures are unambiguous.
- The procedure for constructing and upgrading a database is documented.
- Any implementation conflict is named and assigned to the correct task series.

## Verification

- Compare the documented inventory with all `CREATE TABLE` occurrences and
  ordered migration files.
- Validate the documented migration sequence against migration tests.

## Dependencies

- DOC-001.

## Risks or Notes

- The current implementation may reveal genuinely duplicated schema authority;
  documenting that fact is success, while changing it requires a Backend task.

