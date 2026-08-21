# UI-010E — Administer Digital Asset Trash

## Task ID

`UI-010E` — Status: `Complete`

## Title

Add Administrator Digital Asset Trash Review, Restore, and Purge UI

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [UI Specification](../Specification.md).
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Give administrators a safe management surface for reviewing trashed Album and Photo assets, restoring eligible items, and permanently emptying reviewed Trash scope.

The UI presents Album business status, catalog visibility, and digital-asset
availability as separate facts. It never describes retained Album/Photo
database evidence as deleted when only assets were removed.

## Scope

- Admin Center Trash list, filters, lifecycle state, retention/hold, Album/Photo scope, and safe evidence.
- Administrative visibility into the Album Trash action owned by `UI-037`,
  without duplicating its entity-management workflow.
- Normal Albums ReadModel exclusion for Trashed Albums and explicit historical
  presentation for records whose assets are `DELETED`.
- Restore eligibility, collision/failure presentation, hold/release, individual purge, and reviewed batch empty-Trash flow.
- Operation, Issue, Repair, and affected-entity navigation.
- Role enforcement, stale/replay protection, truthful progress and partial outcomes.

## Out of Scope

- Routine Photo browsing or standalone Photo CRUD in `apps.web`.
- Repair Quarantine, owned by `UI-009`.
- Database Snapshot Restore, owned by `UI-010C`.
- Native macOS library and self-organized Album experiences.

## Dependencies

- `UI-002`, `UI-003`, `UI-007`, and `UI-010` — shared interaction, fixtures, evidence navigation, and Admin shell.
- `BT-033` — blocks all implementation until the lifecycle contract is approved.
- `BT-034` — blocks Album Trash/Restore and Admin Trash list/detail delivery.
- `BT-035` — blocks only permanent purge, empty-Trash, and deleted-asset history
  delivery; it does not block implementation and acceptance of Trash/Restore.
- `UI-037` — supplies the Album-detail move-to-Trash entry and browser-created
  recoverable items used by this task's restore journey.

## Implementation Steps

1. Build Admin Trash list/detail, filters, safe impact summaries, retention,
   hold/release, and restore presentation. Verify Trashed Albums disappear from
   normal Albums without changing their displayed historical business status.
2. Integrate with the Album-page Trash action delivered by `UI-037` and add
   isolated Trash/Restore browser/filesystem acceptance before enabling any
   purge control.
3. After `BT-035`, add individual purge and reviewed batch empty-Trash
   confirmations driven only by Backend eligibility/read models.
4. Add deleted-asset history presentation with `assets_available = false`, no
   open-folder/photo affordance, retained Photo count/bytes, and durable
   Operation evidence.
5. Link durable outcomes and render stale, collision, missing-file, partial,
   and `NeedsRepair` states truthfully; add destructive-path acceptance.

## Acceptance Criteria

- Normal entity pages do not expose Photo browsing or independent Photo deletion.
- Album Trash confirmation includes the Album and contained-Photo count as one management unit.
- Album `status_id`, Trash/catalog state, and asset state are visibly distinct;
  Trash and restore never appear to rewrite Album business status.
- An ineligible Album exposes a specific Backend-provided reason rather than a
  silent disabled button, and direct requests remain Backend-enforced.
- Writer and Admin may execute eligible Album Trash from entity management;
  only Admin may enter or mutate Administrator Trash. Hidden controls never
  substitute for Backend authorization.
- Restore never claims overwrite, and purge never begins without reviewed eligible scope and explicit destructive confirmation.
- Cancelled, unauthorized, stale, repeated, held, and failed actions preserve the specified prior state.
- Successful and partial outcomes match verified filesystem/database state and link to durable evidence.
- Permanently deleted assets leave an accessible historical Album record, but
  the UI offers no action that claims its files or Photos remain available.

## Verification

- Run dedicated Trash browser acceptance twice against disposable roots.
- Run Backend Trash/purge workflow acceptance and UI permission/disclosure regressions.

## Risks or Notes

- UI copy must clearly distinguish Digital Asset Trash, Repair Quarantine, and database Restore.

## Completion Record

- Added Admin Center Digital Asset Trash list/detail routes with lifecycle and
  asset-state filters, retained business status, current-versus-restored
  history, scope, retention, hold, and Operation evidence.
- Added Backend-authorized restore, hold, and release-hold controls with
  reviewed Preview/Execute behavior and explicit blocker presentation.
- Added individual permanent purge and selected eligible empty-Trash review
  with exact typed confirmation and Backend-owned batch scope.
- Added `DELETED` history presentation showing retained Photo/byte tombstone
  evidence without folder, Photo-content, restore, or redispatch affordances.
- Added UI contract coverage for state separation, Backend action ownership,
  restore, hold, purge, batch purge, and durable purge evidence.
