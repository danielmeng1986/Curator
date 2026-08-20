# Operation Logging Specification

## Purpose and scope

This Specification defines the durable record of important Backend actions. Curator uses a database-first, JSONL-secondary model: the persistent `operation` concept is the reliable history and recovery context; JSONL is human-readable diagnostic support and never the only source of truth.

An Operation is not an authorization record. It records a business or operational action that occurred or was attempted.

## Required record content

Every Operation record contains, at minimum:

- stable `operation_uuid`;
- operation type;
- initiator: Web UI, AI Worker, CLI, or other approved Backend actor;
- start and end timestamps;
- status;
- related entity UUIDs where applicable;
- human-readable summary;
- error details when unsuccessful;
- repair state when filesystem repair is relevant;
- recovery context required to understand or continue the operation.

The status vocabulary, error-code taxonomy, and relationship fields in this Specification are stable Backend contracts. Field representation and diagnostic retention remain owning-workflow decisions unless another Specification defines them.

## Lifecycle requirements

An Operation begins before, or at the start of, the material work it records and receives a durable outcome when that work completes or fails. An unresolved filesystem failure must remain linked to its repair state and must not be recorded as a completed success. Follow-up repair or verification is recorded as linked subsequent activity rather than erasing the original outcome.

### Status vocabulary

Every Operation has exactly one of these statuses:

- `Pending`: accepted but material work has not started;
- `Running`: material work is in progress;
- `Succeeded`: material work completed and any required verification succeeded;
- `Failed`: material work ended unsuccessfully and no repair workflow is currently required or active;
- `NeedsRepair`: material work ended unsuccessfully and requires repair or verification before the affected state can be considered resolved;
- `Cancelled`: work was intentionally stopped before verified success.

Normal transitions are `Pending` to `Running`, then `Succeeded`, `Failed`, `NeedsRepair`, or `Cancelled`. A workflow may omit `Pending` only when work starts synchronously with record creation. No workflow-specific private status values are permitted. In particular, unresolved failure or repair state must not be represented by a private status or a success status.

### Error-code taxonomy

Operation status describes lifecycle outcome; an error category and error code describe the cause of an unsuccessful or degraded outcome. They are separate concepts.

When an Operation is unsuccessful, cancelled because of an error, or enters `NeedsRepair`, it must record a stable coarse `error_category` and, where a concrete cause is known, a stable `error_code`. Permitted categories are `validation`, `filesystem`, `database`, `permission`, `conflict`, `external-tool`, and `internal`. Codes refine a category, for example `filesystem.path-not-found`, `filesystem.write-failed`, `database.transaction-failed`, `permission.denied`, `conflict.version-mismatch`, or `external-tool.timeout`. Codes must be documented, stable enough for clients and recovery logic, and must not substitute for the Operation status.

## Creation requirements

| Action type | Operation requirement |
| --- | --- |
| Material write | Record according to the owning workflow policy. |
| Import execution | Required, with per-item outcome/recovery context as needed. |
| Workspace promotion or material batch action | Required. |
| Work Dispatch execution, Group cancellation, or reservation release | Required, linked to the Dispatch Batch/Group and affected Albums. |
| Snapshot and restore | Required. |
| Repair action | Required. |
| Digital Asset Trash, restore, hold change, or permanent asset purge | Required, linked to the retained Album/Photo identity and reviewed scope. |
| Authentication approval, issuance, revocation, or security-relevant event | Required or linked Issue as specified by Authentication. |
| Read-only simple query | Not required by default. |

### Mandatory contextual UUIDs

Every Operation requires its own stable `operation_uuid`. It must additionally include the contextual UUIDs required by its operation family; unrelated UUIDs must not be required merely for uniformity.

| Major operation type | Mandatory contextual UUIDs |
| --- | --- |
| Entity or asset action | `entity_uuid` |
| Digital Asset Trash or restore | Album `entity_uuid`; affected Photo UUIDs or a bounded manifest digest in related-entity evidence |
| Permanent digital-asset purge | Album `entity_uuid`; reviewed asset count/bytes, manifest digest, and related Trash Operation UUID |
| Import execution | `import_uuid` |
| Batch execution or workspace promotion | `batch_uuid` |
| Work Dispatch execution | `batch_uuid`; affected Group and Album UUIDs in bounded related-entity evidence |
| Work Dispatch Group cancellation or release | `group_uuid`, `entity_uuid` for the Album, and the originating `batch_uuid` |
| Repair workflow | `repair_uuid`, `related_operation_uuid` identifying the original failed Operation |
| Device registration | `device_uuid` and/or `registration_uuid`, as applicable to the workflow |
| Issue-driven workflow | `issue_uuid` when the Issue is the tracking anchor |
| Snapshot or restore affecting an entity | `entity_uuid` when an entity is affected; otherwise the workflow's `batch_uuid` or equivalent owning context |

An Operation may carry additional related UUIDs when needed for recovery context. `related_operation_uuid` and `parent_operation_uuid` are used only for durable Operation-to-Operation relationships, not as replacements for the contextual UUID required above.

### Role-based summaries and diagnostics

Operation fields are classified as public summary, operational diagnostics, or sensitive diagnostics. API responses must enforce the following disclosure model:

| Field class | `reader` | `writer` | `admin` | Examples |
| --- | --- | --- | --- | --- |
| Public summary | May read | May read | May read | `operation_uuid`, type, timestamps, status, human-readable summary, outcome, error category/code, related UUIDs, and repair state |
| Operational diagnostics | Must not read | May read when needed for normal workflow execution | May read | recovery instructions, non-sensitive stage results, repair linkage/state, issue linkage, and workflow-safe path or tool outcome summaries |
| Sensitive diagnostics | Must not read | Must not read unless separately authorized by a more restrictive policy | May read only when authorized | stack traces, internal command details, raw tool output, sensitive paths, credentials, tokens, and other protected data |

Sensitive diagnostics must never be exposed to unauthorized API clients. `admin` is the broadest ordinary role, not an automatic authorization to disclose material protected by a stricter access policy.

## JSONL relationship

JSONL may contain diagnostic detail suitable for human investigation. It must reference or be correlatable with the Operation where applicable. Loss, rotation, or parsing failure of JSONL must not erase the durable business/repair outcome stored in the Backend database.

## Error handling and immutability

- An Operation outcome must never be changed to success unless the underlying workflow actually reaches a verified success state.
- A failed filesystem stage after persistence is represented as `NeedsRepair`, not a completed success.
- Existing Operation history is append-only in business meaning: corrections or follow-up repair results are recorded as linked subsequent activity, not by erasing the fact that an earlier action failed.
- Sensitive diagnostic information must not be exposed to unauthorized API clients.

Digital Asset Trash Operation families use `digital_asset_trash`,
`digital_asset_restore`, and `digital_asset_purge`. A successful purge records
verified deletion of asset bytes, not deletion of catalog identity. A failed or
partial asset move/deletion is `NeedsRepair`; it must retain observed inventory
and recovery context and must not be rewritten as success after a later repair.

## Operations and Issues

An Operation records what happened. An Issue records human tracking or follow-up that may be required. They are related records and must not replace or conflate one another.

Operations may reference an Issue through `issue_uuid`; an Issue that tracks an Operation must reference the relevant Operation through `related_operation_uuid` or an equivalent standardized relationship field. Related Operations use `parent_operation_uuid` for direct lineage and `related_operation_uuid` for a non-parent association. For a repair workflow, the repair Operation must contain `repair_uuid` and `related_operation_uuid` for the original failed Operation; the original failed Operation remains intact, and any Issue should reference the same failure and repair chain. Completing repair must not rewrite the original failed Operation as `Succeeded`.

For device registration, the registration Operation remains durable. A follow-up Issue or manual verification is linked as related activity through `issue_uuid` and, where needed, an Operation relationship field; it must not replace the registration Operation.

The exact names of relationship fields may be refined only by a Backend-wide naming decision; the chosen names must be used consistently across all Backend Specifications and implementations.

## Open Questions

The status/error taxonomy, mandatory contextual UUIDs, role-based disclosure model, and Operation/Issue relationships are resolved by this Specification.

## Future extensions

Operation history may later support reporting and archive-health dashboards. Such reporting must use the durable Operation record rather than treat JSONL as a database substitute.
## Operation history query contract

The authenticated versioned collection endpoint accepts optional exact
`status` and `operation_type` filters, plus inclusive ISO-8601 `started_from`
and `started_to` bounds. Results are ordered by `started_at DESC` with the
internal row identity as a deterministic tie-breaker. `limit` is bounded to
1–100.

Pagination uses an opaque keyset cursor bound to the normalized filters. The
cursor resumes strictly after the final item on the preceding page, so newer
Operations created between requests do not shift the remaining result set.
Changing filters while reusing a cursor is invalid. The endpoint returns the
standard collection envelope with total, active filters, sort description,
`has_more`, and `next_cursor` metadata. Role-based field projection applies
before every page is serialized.
