# BT-027 — Integrate Durable Operation Lifecycle into Import

## Task ID

`BT-027` — Status: `Complete`

## Title

Integrate Durable Operation Lifecycle into Import

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), Staged workflow and Error handling and repair sections.
- [Operation Logging](../Specifications/Operation-Logging.md), Lifecycle requirements, Creation requirements, Mandatory contextual UUIDs, and Error handling and immutability sections.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), risk-based snapshot decision requirements.

## Goal

Make every Import execution create and complete a durable Operation lifecycle that truthfully records its `import_uuid`, outcome, error or repair context, and relationship to supporting logs and snapshots.

## Scope

- Inject the shared Operation service into the Import Service and production composition root without bypassing service/repository boundaries.
- Create the Import Operation before material work begins, recording the execution's stable `import_uuid` and initiator.
- Complete the Operation as `Succeeded`, `Failed`, or `NeedsRepair` according to the aggregate durable outcome; persist stable error category/code and recovery context where applicable.
- Correlate workflow-safe change-log and snapshot evidence with the durable Operation without treating logs as the source of truth.
- Add focused integration coverage and make the successful BT-019 action scenarios pass.

## Out of Scope

- Implementing Repair execution or Issue creation for a failed import; the recovery workflow is verified by BT-020.
- Changing Import identity, duplicate, filesystem-action, or snapshot-risk policy.
- Adding a new API endpoint or UI surface.

## Dependencies

- `BT-009` — provides the import persistence and filesystem execution boundary.
- `BT-011` and `BT-012` — provide snapshot and common durable Operation behavior.
- `BT-019` — provides the acceptance scenarios currently exposing the missing Operation records.

## Implementation Steps

1. Define the Import Operation ownership and final-status mapping for successful, validation/database failure, and post-persistence filesystem-failure outcomes.
2. Add the Operation-service dependency at the Import Service composition boundary and create the Operation before material work starts.
3. Persist terminal outcome, stable error category/code, repair state, and workflow-safe recovery context without rewriting historical failure as success.
4. Add or update focused import-operation tests and satisfy the BT-019 `DATABASE_ONLY`, `COPY`, and `MOVE` workflow assertions.

## Acceptance Criteria

- Every executed import has exactly one durable Operation with a distinct `operation_uuid` and the matching `import_uuid`.
- A successful `DATABASE_ONLY`, `COPY`, or `MOVE` execution ends as `Succeeded` only after all required work finishes.
- A failure before durable business change is recorded as unsuccessful with an appropriate stable error category/code.
- A filesystem failure after persistence ends as `NeedsRepair` with recovery context; it is never reported as successful.
- Change-log and snapshot records can be correlated with the Operation, while the database Operation remains authoritative.

## Verification

- Run focused import-operation service tests for success, pre-persistence failure, and post-persistence filesystem failure.
- Run `python3 tools/web_ui/tests/run_regression.py workflow` and confirm the BT-019 successful action scenarios pass.
- Run operations, import, snapshots, and complete regression suites.

## Risks or Notes

- Preserve the separate identities of `operation_uuid` and `import_uuid`; an import execution's contextual UUID does not replace the Operation's own stable identity.
