# Operation Logging Specification

## Purpose and scope

This Specification defines the durable record of important Backend actions. Curator uses a database-first, JSONL-secondary model: the persistent `operation` concept is the reliable history and recovery context; JSONL is human-readable diagnostic support and never the only source of truth.

An Operation is not an authorization record. It records a business or operational action that occurred or was attempted.

## Required record content

Every Operation record contains, at minimum:

- stable operation UUID;
- operation type;
- initiator: Web UI, AI Worker, CLI, or other approved Backend actor;
- start and end timestamps;
- status;
- related entity UUIDs where applicable;
- human-readable summary;
- error details when unsuccessful;
- repair state when filesystem repair is relevant;
- recovery context required to understand or continue the operation.

The exact status vocabulary, error codes, maximum diagnostic retention, and field representation are Specification decisions still to be resolved below.

## Lifecycle requirements

An Operation begins before, or at the start of, the material work it records and receives a durable outcome when that work completes or fails. An unresolved filesystem failure must remain linked to its repair state and must not be recorded as a completed success. Follow-up repair or verification is recorded as linked subsequent activity rather than erasing the original outcome.

The exact Operation status vocabulary and legal transitions remain unresolved. They must be defined here before implementation; a workflow may not invent private status values that conceal an unresolved failure or repair.

## Creation requirements

| Action type | Operation requirement |
| --- | --- |
| Material write | Record according to the owning workflow policy. |
| Import execution | Required, with per-item outcome/recovery context as needed. |
| Workspace promotion or material batch action | Required. |
| Snapshot and restore | Required. |
| Repair action | Required. |
| Authentication approval, issuance, revocation, or security-relevant event | Required or linked Issue as specified by Authentication. |
| Read-only simple query | Not required by default. |

## JSONL relationship

JSONL may contain diagnostic detail suitable for human investigation. It must reference or be correlatable with the Operation where applicable. Loss, rotation, or parsing failure of JSONL must not erase the durable business/repair outcome stored in the Backend database.

## Error handling and immutability

- An Operation outcome must never be changed to success unless the underlying workflow actually reaches a verified success state.
- A failed filesystem stage after persistence is represented as `NeedsRepair`, not a completed success.
- Existing Operation history is append-only in business meaning: corrections or follow-up repair results are recorded as linked subsequent activity, not by erasing the fact that an earlier action failed.
- Sensitive diagnostic information must not be exposed to unauthorized API clients.

## Open Questions

- What exact status values and error-code taxonomy are required?
- Which related UUIDs are mandatory for each operation type?
- Which summaries and diagnostic fields may be shown to `reader`, `writer`, and `admin` clients?
- How are related Operations and Issues linked for a repair or device-registration workflow?

## Future extensions

Operation history may later support reporting and archive-health dashboards. Such reporting must use the durable Operation record rather than treat JSONL as a database substitute.
