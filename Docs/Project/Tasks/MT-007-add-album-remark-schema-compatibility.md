# MT-007 — Add Album Remark Schema Compatibility

## Task ID

`MT-007` — Status: `Proposed`

## Title

Add Album Remark Schema Compatibility

## Related Specification(s)

- [Curator Domain Model](../../Database/Curator_Domain_Model.md), `album.remark` domain rule.
- [Curator Database Model](../../Database/Curator_Database_Model.md), `ALBUM` schema.
- [Workspace Workflow](../../Backend/Specifications/Workspace-Workflow.md), `workspace_album` Review and promotion contract.

## Goal

Add the permanent `album.remark` field through a versioned, migration-safe
schema change, and keep all Backend read/write contracts compatible with both
the migration process and the target schema.

## Scope

- Add a versioned schema migration that preserves all existing Album rows and
  makes `album.remark` nullable.
- Update Backend repository read/write models and test fixtures that own Album
  schema assumptions.
- Verify that the live-database migration is repeatable, recoverable, and does
  not alter unrelated Album fields, relationships, or paths.

## Out of Scope

- Promoting or archiving any `workspace_album` record.
- Introducing reviewer decisions, approval UI, or a new normal import path.

## Dependencies

- `MT-001` — versioned database migration/schema source location.
- `BT-031` — approved permanent `album.remark` semantics.

## Implementation Steps

1. Inspect the target live schema and take a timestamped, verified backup
   before any schema write.
2. Add an idempotent versioned migration for nullable `album.remark`, with
   rollback/recovery instructions appropriate to the active SQLite database.
3. Update Backend-owned Album repositories, read models, and disposable test
   schemas to preserve the field without changing existing API meanings.
4. Add focused migration and compatibility tests, then run the Backend
   regression suite against disposable databases.

## Acceptance Criteria

- Existing Albums retain every prior value; their new `remark` is `NULL` until
  explicitly populated.
- A rerun recognizes the completed schema change and neither fails nor loses
  data.
- Album read/write behavior remains compatible for callers that do not supply
  `remark`.
- No database image, backup, or runtime data is added to Git.

## Verification

- Run migration tests on a representative disposable pre-migration database,
  including a repeat run and schema integrity check.
- Run `python3 tools/web_ui/tests/run_regression.py all` successfully.
- Inspect the migration backup and the working tree before committing.

## Risks or Notes

- The migration must inspect the live schema rather than assuming every local
  database has the same prior revision.
- This task is deliberately separate from history promotion so a schema change
  can be recovered independently of business-data materialization.
