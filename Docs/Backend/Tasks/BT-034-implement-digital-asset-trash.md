# BT-034 — Implement Digital Asset Trash

## Task ID

`BT-034` — Status: `Ready`

## Title

Implement Recoverable Album and Photo Trash Transitions

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [Operation Logging](../Specifications/Operation-Logging.md).
- [Authentication](../Specifications/Authentication.md).

## Goal

Implement recoverable, verified movement of Album asset units and individually selected Photos into and out of Digital Asset Trash.

Trash changes catalog visibility and asset location while preserving Album,
Photo, relationship, AI Work, Review, Operation, and public-identifier rows.
Album business `status_id` is unchanged.

## Scope

- Migration-safe `catalog_state` and `asset_state` persistence, lifecycle
  timestamps/actors/Operation identity, versioning, and stable read models.
- Default Album collection exclusion for `catalog_state = TRASHED`, plus
  explicit Admin Trash and historical-asset read models.
- Centralized Trash eligibility/readiness evaluation with stable blocker codes
  for active reservation, unreleased Group, unfinished Work Item/Review/
  promotion, unclosed Workspace, and active Operation/Issue/Repair ownership.
- Impact preview/version and Writer/Admin-authorized Album Trash entry points for `apps.web`.
- Photo-level entry points suitable for a future native client.
- Safe filesystem moves below configured roots, restore collision protection, retention/hold metadata, and post-action verification.
- Durable Operation and Issue/Repair hand-off for every attempted material transition.

## Out of Scope

- Permanent filesystem deletion, owned by `BT-035`.
- Repair Quarantine actions already owned by `BT-029`.
- Web or native application presentation.
- Physical deletion of Album, Photo, relationship, AI Work, Review, or
  Operation database rows.

## Dependencies

- `BT-033` — supplies the approved lifecycle specification and acceptance matrix.
- `BT-011`, `BT-012`, `BT-013`, `BT-015`, and `BT-029` — recovery, evidence, authorization, and failure boundaries.

## Implementation Steps

1. Add lifecycle persistence and migrate existing rows to
   `catalog_state = ACTIVE`, `asset_state = PRESENT` without changing
   `status_id`.
2. Update normal Album list/count/detail contracts to exclude Trashed records
   by default, and add explicit Admin Trash/detail/history read models.
3. Implement a shared readiness service returning `can_trash`, `can_restore`,
   stable blockers, impacted Photo count/bytes, version, and safe navigation
   references.
4. Implement versioned preview, Trash, list/detail, restore, hold, and release
   services and `/api/v1` endpoints. Retire or reject the legacy Album hard
   delete endpoint with a stable business response.
5. Coordinate safe filesystem movement and lifecycle updates, verify the final
   outcome, and hand partial results to explicit `NEEDS_REPAIR` evidence.
6. Add disposable database/filesystem workflow acceptance for Album and Photo
   scopes, including active AI Work and completed historical AI Work.

## Acceptance Criteria

- Album Trash scope includes every contained Photo and names the reviewed impact before mutation.
- `status_id` is unchanged across Trash and restore; the same Album and Photo
  IDs, UUIDs, relationships, and AI history remain present.
- Any active or not-fully-closed Work Dispatch/Review/Workspace dependency
  returns a structured blocker and produces zero lifecycle/filesystem mutation.
- Normal `GET /albums` no longer returns Trashed Albums, while Admin Trash and
  historical routes can still resolve them.
- No path can escape configured active-library or Trash roots, and restore never overwrites an occupied destination.
- Cancellation, invalid scope, unauthorized access, stale preview, and replay leave filesystem and durable state unchanged.
- A successful transition updates filesystem and database lifecycle consistently and leaves linked Operation evidence.
- A partial outcome is never reported as success or rolled back by claim; it remains recoverable through Issue/Repair evidence.

## Verification

- Run focused Trash/restore workflows twice on disposable roots.
- Run snapshot, Operation, authentication, Issue/Repair, Quarantine, and complete Backend regression suites.

## Risks or Notes

- Do not implement this task by calling the existing hard-delete Album repository path.
- A first release may separate catalog hiding from asynchronous filesystem
  movement, but it must expose the truthful intermediate `asset_state` and may
  not report the operation as fully Trashed before verification succeeds.
