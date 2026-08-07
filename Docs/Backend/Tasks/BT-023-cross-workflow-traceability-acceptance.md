# BT-023 — Verify Cross-Workflow Traceability

## Task ID

`BT-023` — Status: `Proposed`

## Title

Verify Cross-Workflow Traceability

## Related Specification(s)

- [Operation Logging](../Specifications/Operation-Logging.md), Required record content, Lifecycle requirements, Mandatory contextual UUIDs, Role-based summaries and diagnostics, and Operations and Issues sections.
- [Issue Management](../Specifications/Issue-Management.md), linkage and lifecycle requirements.
- [Import Workflow](../Specifications/Import-Workflow.md), Operation and snapshot requirements.
- [Repair Workflow](../Specifications/Repair-Workflow.md), Error handling, Operations, and Issues section.
- [Authentication](../Specifications/Authentication.md), Access and error handling section.

## Goal

Verify that representative material workflows leave a complete, truthful, and authorization-safe durable trail across Operations, Issues, snapshots, and related entity identifiers.

## Scope

- Reuse workflow scenarios to inspect successful import, failed import/repair, snapshot or restore, and security-relevant authentication activity.
- Assert required statuses, contextual UUIDs, parent/related Operation links, Issue links, error category/code, and append-only historical meaning.
- Verify role-sensitive API/read-model disclosure using ordinary reader, writer, and administrator principals where the relevant endpoint exists.

## Out of Scope

- Building reporting dashboards or a new audit-log product.
- Treating JSONL as a substitute for durable Operation data.
- Duplicating detailed workflow success/failure scenarios owned by the source workflow tasks.

## Dependencies

- `BT-019`, `BT-020`, `BT-021`, and `BT-022` — provide representative workflow outcomes and fixtures.
- `BT-011`, `BT-012`, `BT-013`, and `BT-015` — provide snapshot, Operation, authorization, and Issue behavior under test.

## Implementation Steps

1. Select representative completed and unresolved workflow states from the focused acceptance scenarios.
2. Add cross-record assertions for required identifiers, status/error semantics, and immutable history.
3. Add role-based disclosure assertions at the service or API read boundary.
4. Document any missing traceability field or disclosure behavior as a readiness gap against its Specification.

## Acceptance Criteria

- Each representative material action has the required durable Operation context and final truthful status.
- Repair records remain linked to their original failed Operation without rewriting the original outcome.
- Required Issues, snapshots, and contextual UUIDs are consistently discoverable through their specified relationships.
- Sensitive diagnostics are not disclosed to roles that the Specification forbids from reading them.

## Verification

- Run the focused cross-workflow traceability scenarios.
- Run operations, authentication, snapshots, and issue-related regression coverage, then the complete suite.

## Risks or Notes

- Keep assertions at stable record and API boundaries; do not couple this task to JSONL formatting or internal logging implementation.
