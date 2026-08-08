# BT-035 — Implement Digital Asset Trash Purge

## Task ID

`BT-035` — Status: `Blocked`

## Title

Implement Administrator-Confirmed Permanent Digital Asset Purge

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [Operation Logging](../Specifications/Operation-Logging.md).
- [Authentication](../Specifications/Authentication.md).

## Goal

Implement the final, explicitly destructive removal of eligible assets from Digital Asset Trash while preserving the evidence required to explain what was removed and any failed or partial outcome.

## Scope

- Purge eligibility/readiness preview with stable identity/version.
- Admin-only individual and reviewed batch purge.
- Retention and hold enforcement, filesystem deletion, database finalization, and verification.
- Idempotency, replay/stale protection, Operation evidence, and Issue/Repair hand-off.

## Out of Scope

- Moving active assets into Trash or restoring them, owned by `BT-034`.
- Repair Quarantine retention cleanup and database Snapshot cleanup.
- Web UI, owned by `UI-010E`.

## Dependencies

- `BT-033` and `BT-034` — blocked until the normative contract and recoverable Trash lifecycle exist.
- `BT-012`, `BT-013`, and `BT-015` — Operation, Admin authorization, and failure escalation.

## Implementation Steps

1. Implement purge eligibility and impact preview read models.
2. Implement protected individual and batch purge with version and hold checks.
3. Verify filesystem/database outcomes and persist minimal non-secret historical evidence required by specification.
4. Add destructive-path acceptance using disposable roots only.

## Acceptance Criteria

- Only eligible Trash items can be purged, and only an Admin can authorize the action.
- Confirmation identifies Album/Photo scope and consequences without unnecessary absolute-path disclosure.
- Hold, retention, stale, replay, missing-file, and collision rules produce specified outcomes without deleting unrelated assets.
- Successful purge is verified; partial failure is truthful and linked to recoverable Issue/Repair evidence.
- Tests never target a production-like archive, Trash, Quarantine, or database path.

## Verification

- Run purge workflows twice on isolated disposable roots.
- Run authorization, Operation, Issue/Repair, Trash, and complete Backend regression suites.

## Risks or Notes

- This task is intentionally separate from recoverable Trash because permanent deletion requires a stronger review and test boundary.
