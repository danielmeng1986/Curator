# BT-029 — Implement Quarantine and Restore Safety Workflow

## Task ID

`BT-029` — Status: `Complete`

## Title

Implement Quarantine and Restore Safety Workflow

## Related Specification(s)

- [Repair Workflow](../Specifications/Repair-Workflow.md), Normative quarantine policy and Snapshot requirements.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), risk-based snapshot policy.
- [Authentication](../Specifications/Authentication.md), administrator authorization model.
- [Operation Logging](../Specifications/Operation-Logging.md), durable material-work evidence.

## Goal

Implement safe, administrator-controlled quarantine and restoration of managed directories, retaining the metadata, authorization checks, snapshot decisions, and verification required by the Repair Workflow.

## Scope

- Persist quarantine identity, original path, repair and Operation linkage, reason, timestamps, retention/hold data, and content inventory.
- Move a directory intact to a unique location below a Curator-controlled quarantine root outside the managed archive namespace.
- Restrict list, inspect, restore, hold/extend, and release actions to administrators; expose only repair-safe identity/status to normal repair clients.
- Validate restore destination, prohibit overwrite, create required pre-action snapshots, and require post-action consistency verification.
- Record durable Operations and audit outcomes for quarantine, restore, and retention decisions.

## Out of Scope

- Permanent expiry deletion beyond the retention workflow currently implemented for snapshots.
- UI presentation and manual operator workflow screens.
- Altering canonical path or repair classification rules owned by `BT-028`.

## Dependencies

- `BT-028` — supplies the repair policy/action boundary and suppression behavior.
- `BT-011`, `BT-012`, `BT-013`, and `BT-015` — snapshot, Operation, authentication, and Issue boundaries.

## Implementation Steps

1. Add migration-safe quarantine persistence and repository read models.
2. Implement isolated filesystem move, inventory, authorization, audit, and Operation behavior for quarantine.
3. Implement restore validation, conflict rejection, risk-based snapshot gating, and verification hand-off.
4. Add focused filesystem workflow tests using disposable archive and quarantine roots.

## Acceptance Criteria

- Quarantine never deletes data, cannot escape its configured root, and preserves the full directory and required durable metadata.
- Only an administrator can inspect or mutate quarantine records; unauthorized attempts cause no filesystem or database changes.
- Restore rejects an occupied or unsafe destination without overwriting content.
- Every required snapshot succeeds before a protected action begins; snapshot failure leaves the repair unresolved and the filesystem unchanged.
- Quarantine and restore attempts leave truthful linked Operation and audit evidence, including failed checks.

## Verification

- Run focused quarantine/restore workflow tests on disposable roots.
- Run repair, snapshots, authentication, operations, and complete Backend regression groups.
- Resume the blocked `BT-022` acceptance task.

## Risks or Notes

- Restoration and expiry removal are materially destructive when misclassified; preserve the snapshot gate and do not add a bypass for normal repair clients.
