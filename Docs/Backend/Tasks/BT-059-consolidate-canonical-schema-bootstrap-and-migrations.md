# BT-059 — Consolidate Canonical Schema Bootstrap and Ordered Migrations

## Task ID

`BT-059` — Status: `Proposed`

## Goal

Establish one versioned, testable Backend-owned path that creates the complete
Curator schema from an empty SQLite database and upgrades supported existing
databases through all reviewed migrations without relying on Repository access
order.

## Related Specifications

- Backend Architecture database ownership and migration boundary.
- Repository Specification.
- Snapshot Specification for pre-migration verified backups.
- `Docs/Database/Schema-Source-of-Truth.md` gap inventory.

## Scope

- Define/version the base asset-catalog schema.
- Integrate guarded historical adoption and ordered migrations `0001` onward.
- Move Authentication and operational workflow table ownership into reviewed
  migrations or explicitly constrain Repository DDL to verified compatibility.
- Record each applied migration independently and rerun safely.
- Preserve existing data, constraints, indexes, archived history, and recovery evidence.
- Provide empty-database, legacy-adoption, partial-upgrade, replay, failure, and
  rollback acceptance tests.

## Out of Scope

- Changing business fields or workflow behavior merely to simplify migration.
- Automatic migration during ordinary Backend HTTP startup without a separately
  approved operational policy.
- Running against production data before a reviewed dry run and backup.

## Acceptance Criteria

- One documented command creates a complete disposable current database from empty.
- The same command upgrades each supported prior shape in deterministic order.
- Repository construction order cannot change final schema.
- Every migration receives a durable unique record and safe replay behavior.
- Pre-write backup, integrity check, FK check, and actionable recovery output remain mandatory.
- Schema introspection matches the DBDOC catalog and drift gate.

## Verification

- Migration tests for empty, existing v0.2, archived Workspace, and partial AI schemas.
- Injected failure proves transaction/backup recovery behavior.
- Backend workflow-readiness twice and full regression once.

## Dependencies

- DBDOC-001 documents the current split authority.
- Complete controlling migration/adoption Specification decisions before implementation.

## Risks or Notes

- This task must distinguish adoption of a matching pre-existing object from
  silently accepting an incompatible object with the same name.

