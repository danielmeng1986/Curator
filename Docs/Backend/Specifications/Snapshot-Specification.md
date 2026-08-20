# Snapshot Specification

## Purpose and scope

This Specification defines the required behavior for recoverable database snapshots. SQLite remains the current implementation, but snapshot policy is expressed in terms of risk and recoverability rather than a database engine.

## Policy

Snapshot decisions are based on operation risk and recoverability, not on row count alone. A large operation is not automatically high-risk, and a small operation may be high-risk when it is hard to reverse or could compromise recoverable state. Normal single-entity CRUD generally requires an Operation record but not a snapshot.

| Risk bucket | Operation category | Snapshot expectation |
| --- | --- |
| Always high-risk | Data migration | Required before the high-risk change. |
| Always high-risk | Restore | Required before altering recoverable state; see the restore workflow below. |
| Conditionally high-risk | Bulk import or bulk delete | Snapshot candidate; required when the service-side risk assessment classifies the operation as high-risk. |
| Conditionally high-risk | Bulk filesystem rename or quarantine | Snapshot candidate; required when the service-side risk assessment classifies the operation as high-risk. |
| Conditionally high-risk | Batch Digital Asset Trash, restore, or permanent asset purge | Snapshot candidate for database recoverability; required when service-side risk assessment classifies the database transition as high-risk. |
| Conditionally high-risk | Workspace-to-production promotion | Snapshot candidate; required when the service-side risk assessment classifies the operation as high-risk. |
| Conditionally high-risk | Cross-table relationship rebuild | Snapshot candidate; required when the service-side risk assessment classifies the operation as high-risk. |
| Ordinary | Single-entity CRUD | No snapshot by default; Operation record required according to policy. |

## Workflow

```text
Proposed operation
  -> Service assesses operation risk and recoverability
  -> snapshot required?
      -> yes: create and record snapshot reference
      -> no: continue without snapshot
  -> execute operation
  -> record outcome and recovery context
```

If a required snapshot cannot be created, the high-risk operation must not proceed as though recoverability were available. The resulting rejection or failure is recorded.

## Snapshot metadata, retention, and restore

A snapshot record must retain, at minimum:

- The initiating Operation identifier, where applicable, and enough information to identify the initiating operation.
- Its creation time.
- Its reason and risk category.
- Its protection state and retention class.
- Its restore relationship, including the relevant restore Operation and, where applicable, the restore target snapshot and the safety snapshot created before that restore.
- Implementation-specific recovery information sufficient for the active database implementation to identify and use the snapshot later.

This metadata is required so validation and cleanup can be applied deterministically. A snapshot is valid only if it can be identified and used by the active database implementation's recovery process.

Snapshots use the following retention classes:

| Retention class | Policy |
| --- | --- |
| `ordinary` | Default class for ordinary snapshots; retain for 30 days after creation. |
| `high-risk` | Class for snapshots created for high-risk operations; retain for 180 days after creation. |
| Protected | A protection state that may be applied to a snapshot in either retention class. A protected snapshot must never be deleted by automated cleanup unless protection has been explicitly removed. |

Cleanup eligibility is a hard gate: automated cleanup may delete a snapshot only when its retention period has expired and it is not protected. It must not treat either condition as a soft recommendation.

Restore is an explicit high-risk workflow. Before altering recoverable state, it must create a safety snapshot and create an Operation record. Through `/api/v1`, restore must first be represented as a distinct pending-confirmation step, not as an immediate effect. The API workflow must express at least `pending_confirmation`, `confirmed`, `executing`, `completed`, `failed`, and `cancelled` states, or an equivalent explicit state model. Confirmation is required before execution begins.

Snapshots provide recovery material only. They do not replace Operation records, which describe what was attempted and why, or JSONL diagnostic logs, which retain diagnostic detail. Each remains required for its own purpose.

A database snapshot never contains or restores digital-asset bytes and must not
be presented as making permanent asset purge reversible. Lifecycle-schema
migration requires a snapshot. Ordinary single-Album Trash or restore does not
require a database snapshot solely because it moves files, but still requires
the Digital Asset Trash preview, Operation, filesystem verification, and repair
policy. Purge remains irreversible for verified deleted bytes whether or not a
database snapshot is required by risk assessment.

## Validation and error handling

- Restore requires an explicit selected target and must not overwrite recoverable state without a safety snapshot.
- Retention cleanup must enforce the cleanup-eligibility gate defined above.
- Failure to create, restore, or validate a snapshot is an Operation outcome and must be visible to the initiator.

## Open Questions

- What service-side signals and thresholds determine whether a conditionally high-risk candidate is classified as high-risk?
- Should retention durations be configurable by deployment, while preserving the `ordinary`, `high-risk`, and protected cleanup rules?

## Future extensions

When PostgreSQL becomes active, its backup and restore implementation may differ from SQLite file snapshots, but it must honor the same risk, metadata, safety, and Operation-record behavior.
