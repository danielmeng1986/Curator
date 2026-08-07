# MT-008 — Close and Archive Historical Workspace Albums

## Task ID

`MT-008` — Status: `Completed`

## Title

Close and Archive Historical Workspace Albums

## Related Specification(s)

- [Workspace Workflow](../../Backend/Specifications/Workspace-Workflow.md), `workspace_album` Review and promotion contract.
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md), truthful, append-only Operation history.
- [Snapshot Specification](../../Backend/Specifications/Snapshot-Specification.md), Workspace-to-production promotion.
- [Curator Database Model](../../Database/Curator_Database_Model.md), Workspace-to-Album migration semantics.

## Goal

Safely complete the historical `workspace_album` collection: validate approved
records, materialize any remaining permanent Album data and relationships,
then close and archive the Workspace records while preserving recovery and
traceability evidence.

## Scope

- Inventory and classify every historical Workspace record as already
  materialized, promotable, returned for correction, rejected, or invalid.
- Materialize approved records using the specified two-phase `album`,
  `album_model`, and `album_relation` mapping, including canonical paths and
  `album_id` back-references.
- Create truthful Operations, apply snapshot risk decisions, validate results,
  close completed records, and archive the historical collection.
- Provide dry-run reporting, resumability, and focused workflow acceptance
  coverage using disposable database and filesystem fixtures.

## Out of Scope

- Creating a new general-purpose `workspace_album` import route or UI.
- Defining the schema or Review contract for future AI Worker Workspace
  datasets.
- Deleting archived Workspace history or treating it as a replacement for
  permanent Album data.

## Dependencies

- `MT-007` — permanent `album.remark` schema compatibility.
- `BT-031` — approved Review, promotion, and archival contract.
- `MT-001` — versioned runtime and database-migration boundaries.

## Implementation Steps

1. Take and verify a timestamped backup; run an inventory-only dry run that
   reports every record's classification and unresolved dependency.
2. Implement service-owned validation and resumable two-phase materialization
   without filesystem mutation; reject conflicts and incomplete relationship
   sets before permanent writes.
3. Record Operations, snapshots where risk requires them, decision/audit
   evidence, and exact Workspace-to-permanent links.
4. Verify the materialized set, transition successful/rejected historical rows
   to `Closed`, archive the collection, and add acceptance tests for success,
   invalid records, rollback, and resume.

## Acceptance Criteria

- Every historical Workspace row has an explicit final classification; none is
  silently skipped.
- Each successful materialization has one durable `album_id` back-reference,
  correct `album_model` records, valid canonical `album.path`, and only valid
  non-self `BELONGS_TO` relationships.
- A validation, snapshot, or write failure does not claim success or leave an
  untracked partial permanent materialization.
- Closed and archived Workspace records remain traceable to their Operations
  and permanent Albums; no routine client can use them as active input.

## Verification

- Run dry-run and apply scenarios against disposable copies of representative
  historical data, including repeat/resume and conflict cases.
- Verify foreign keys, relationship uniqueness, canonical path uniqueness,
  row counts, and Operation links after each scenario.
- Run `python3 -m apps.backend.tests.run_regression workflow-readiness` twice
  and `python3 -m apps.backend.tests.run_regression all` successfully.

## Risks or Notes

- This is a business-data migration: it must never run against the live
  database without an explicit, verified backup and reviewed dry-run report.
- Existing direct imports to permanent Album data remain the normal path; this
  task retires a historical Workspace collection rather than reviving it.

## Completion Record

- The live dry run classified all remaining historical rows as already
  materialized; permanent links, paths, and relations were verified before
  archival.
- A curator-directed duplicate cleanup removed one redundant Workspace and
  permanent Album record after filesystem verification, with a verified backup
  and durable Operation record.
- The versioned archival migration records a verified backup, durable archive
  Operation, row classification, archive time, and `archived_retired` lifecycle
  state. A rerun is a no-op.
