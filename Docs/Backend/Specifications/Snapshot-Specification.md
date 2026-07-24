# Snapshot Specification

## Purpose and scope

This Specification defines the required behavior for recoverable database snapshots. SQLite remains the current implementation, but snapshot policy is expressed in terms of risk and recoverability rather than a database engine.

## Policy

Snapshot decisions are based primarily on operation risk, not simply the number of changed rows. Normal single-entity CRUD generally requires an Operation record but not a snapshot.

| Operation category | Snapshot expectation |
| --- | --- |
| Data migration or restore | Required before the high-risk change. |
| Bulk import or bulk delete | Snapshot candidate; required when classified high-risk. |
| Bulk filesystem rename or quarantine | Snapshot candidate; required when classified hard to reverse. |
| Workspace-to-production promotion | Snapshot candidate. |
| Cross-table relationship rebuild | Snapshot candidate. |
| Ordinary single-entity CRUD | No snapshot by default; Operation record required according to policy. |

## Workflow

```text
Proposed operation
  -> Service assesses risk category
  -> snapshot required?
      -> yes: create and record snapshot reference
      -> no: continue without snapshot
  -> execute operation
  -> record outcome and recovery context
```

If a required snapshot cannot be created, the high-risk operation must not proceed as though recoverability were available. The resulting rejection or failure is recorded.

## Snapshot metadata and restore

A snapshot record must be attributable to the initiating operation where applicable and retain enough metadata to identify its creation time, reason/risk category, protection/retention state, and restore relationship. Restore is itself a high-risk operation: it creates a safety snapshot before altering recoverable state and creates an Operation record.

Snapshots do not replace Operation records or JSONL diagnostic logs. They provide recovery material; Operation records describe what was attempted and why.

## Validation and error handling

- A snapshot is valid only if it can later be identified and used by the active database implementation's recovery process.
- Restore requires an explicit selected target and must not overwrite recoverable state without a safety snapshot.
- Retention cleanup must not silently remove snapshots classified as protected.
- Failure to create, restore, or validate a snapshot is an Operation outcome and must be visible to the initiator.

## Open Questions

- Which candidate categories are always high-risk versus conditionally high-risk?
- What retention periods and protected-snapshot rules apply?
- What exact metadata is required for snapshot validation and cleanup?
- How is restore confirmation represented through `/api/v1`?

## Future extensions

When PostgreSQL becomes active, its backup and restore implementation may differ from SQLite file snapshots, but it must honor the same risk, metadata, safety, and Operation-record behavior.
