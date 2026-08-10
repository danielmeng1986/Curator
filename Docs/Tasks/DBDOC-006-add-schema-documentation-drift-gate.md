# DBDOC-006 — Add Schema Documentation Drift Gate

## Task ID

`DBDOC-006` — Status: `Proposed`

## Goal

Add a deterministic check that detects when the initialized database schema and
the documented Schema Catalog diverge.

## Scope

- Define a machine-readable schema inventory derived from, or colocated with,
  the human-readable catalog.
- Build a disposable database using the authoritative initialization/migration path.
- Extract tables, columns, primary/foreign keys, unique/check constraints where
  reliably available, and indexes.
- Compare documented and actual inventory with actionable failure output.
- Add the check to the appropriate documentation or Backend readiness command.

## Out of Scope

- Testing business workflow semantics already covered by Backend regression.
- Connecting to or modifying a production/runtime database.
- Parsing Mermaid diagrams as the schema authority.

## Inputs and Authority

- DOC-001 and DBDOC-001 authority rules.
- DBDOC-002 catalog contract.
- Backend migration runner and disposable test foundation.

## Deliverables

- A repository-owned schema-documentation verification command.
- Machine-readable current schema inventory with documented generation/editing rules.
- Failure output identifying undocumented, missing, or structurally changed objects.
- Updated Database README and test/readiness documentation.

## Acceptance Criteria

- The check runs against disposable resources and never opens the live database.
- Adding/removing/changing a table, material column, FK, or index without a
  catalog update fails deterministically.
- Historical and SQLite-internal tables have explicit inclusion/exclusion rules.
- A clean current checkout passes, and an intentional fixture drift is proven to fail.

## Verification

- Run the gate twice from clean disposable databases.
- Exercise at least one added-table, changed-column, changed-FK, and changed-index failure fixture.
- Run the existing Backend migration and full regression suites afterward.

## Dependencies

- DOC-001.
- DBDOC-001 through DBDOC-005.
- DOC-002 through DOC-004.

## Risks or Notes

- SQLite does not expose every original CHECK expression uniformly. The gate
  must document any intentionally unsupported comparison rather than claim full coverage.

