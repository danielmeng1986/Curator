# DBDOC-006 — Add Schema Documentation Drift Gate

## Task ID

`DBDOC-006` — Status: `Complete`

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
- BT-059 must provide the canonical empty-database bootstrap and ordered
  migration path before this gate can introspect authoritative current schema.

## Risks or Notes

- SQLite does not expose every original CHECK expression uniformly. The gate
  must document any intentionally unsupported comparison rather than claim full coverage.

## Blocking Record

- DBDOC-001 verified that no single current path builds the complete database
  from empty: the default runner applies only `0001`, later migration SQL is not
  iterated by it, and several active tables are created defensively by Repository use.
- Building a documentation-only database constructor would create another
  schema authority and make the proposed drift gate self-validating rather than truthful.
- BT-059 now owns canonical bootstrap, ordered adoption/migration, and disposable
  reconstruction. Resume DBDOC-006 after BT-059 passes its migration acceptance.
- No runtime database, migration, or schema behavior was changed by this blocked task.

## Completion Record

- BT-059 supplied the canonical disposable empty-database build and ordered migrations.
- Added a committed machine-readable inventory plus `tools/check_schema_docs.py`.
- The gate compares tables, columns, FKs, unique/explicit indexes, migration
  order, and Schema Catalog table coverage; SQLite CHECK text is explicitly excluded.
- Added clean, added-table, changed-column, changed-FK, and changed-index acceptance tests.
- The gate passed twice, followed by Backend workflow-readiness and full regression.
