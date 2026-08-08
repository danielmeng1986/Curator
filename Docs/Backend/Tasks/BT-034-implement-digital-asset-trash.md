# BT-034 — Implement Digital Asset Trash

## Task ID

`BT-034` — Status: `Blocked`

## Title

Implement Recoverable Album and Photo Trash Transitions

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [Operation Logging](../Specifications/Operation-Logging.md).
- [Authentication](../Specifications/Authentication.md).

## Goal

Implement recoverable, verified movement of Album asset units and individually selected Photos into and out of Digital Asset Trash.

## Scope

- Migration-safe lifecycle persistence and stable read models.
- Impact preview/version and Admin-authorized Album Trash entry points for `apps.web`.
- Photo-level entry points suitable for a future native client.
- Safe filesystem moves below configured roots, restore collision protection, retention/hold metadata, and post-action verification.
- Durable Operation and Issue/Repair hand-off for every attempted material transition.

## Out of Scope

- Permanent filesystem deletion, owned by `BT-035`.
- Repair Quarantine actions already owned by `BT-029`.
- Web or native application presentation.

## Dependencies

- `BT-033` — blocked until the lifecycle specification and acceptance matrix are complete.
- `BT-011`, `BT-012`, `BT-013`, `BT-015`, and `BT-029` — recovery, evidence, authorization, and failure boundaries.

## Implementation Steps

1. Add lifecycle persistence, repositories, and safe read models.
2. Implement versioned preview, Trash, list/detail, restore, hold, and release services and `/api/v1` endpoints.
3. Add filesystem verification and explicit `NeedsRepair` hand-off for partial outcomes.
4. Add disposable database/filesystem workflow acceptance for Album and Photo scopes.

## Acceptance Criteria

- Album Trash scope includes every contained Photo and names the reviewed impact before mutation.
- No path can escape configured active-library or Trash roots, and restore never overwrites an occupied destination.
- Cancellation, invalid scope, unauthorized access, stale preview, and replay leave filesystem and durable state unchanged.
- A successful transition updates filesystem and database lifecycle consistently and leaves linked Operation evidence.
- A partial outcome is never reported as success or rolled back by claim; it remains recoverable through Issue/Repair evidence.

## Verification

- Run focused Trash/restore workflows twice on disposable roots.
- Run snapshot, Operation, authentication, Issue/Repair, Quarantine, and complete Backend regression suites.

## Risks or Notes

- Do not implement this task by calling the existing hard-delete Album repository path.
