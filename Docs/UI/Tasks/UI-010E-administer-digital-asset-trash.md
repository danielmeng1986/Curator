# UI-010E — Administer Digital Asset Trash

## Task ID

`UI-010E` — Status: `Blocked`

## Title

Add Administrator Digital Asset Trash Review, Restore, and Purge UI

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md).
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Give administrators a safe management surface for reviewing trashed Album and Photo assets, restoring eligible items, and permanently emptying reviewed Trash scope.

## Scope

- Admin Center Trash list, filters, lifecycle state, retention/hold, Album/Photo scope, and safe evidence.
- Album-level Trash impact preview and confirmation initiated from entity management.
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
- `BT-033`, `BT-034`, and `BT-035` — blocked until lifecycle, recoverable actions, and purge contracts exist.

## Implementation Steps

1. Build Admin Trash list/detail, filters, safe impact summaries, retention, and hold presentation.
2. Add Album Trash, restore, hold/release, purge, and empty-Trash confirmations driven only by Backend policy/read models.
3. Link durable outcomes and render stale, collision, missing-file, partial, and `NeedsRepair` states truthfully.
4. Add isolated browser/filesystem acceptance for role separation and every destructive boundary.

## Acceptance Criteria

- Normal entity pages do not expose Photo browsing or independent Photo deletion.
- Album Trash confirmation includes the Album and contained-Photo count as one management unit.
- Only Admin users can enter or mutate Trash; hidden controls never substitute for Backend authorization.
- Restore never claims overwrite, and purge never begins without reviewed eligible scope and explicit destructive confirmation.
- Cancelled, unauthorized, stale, repeated, held, and failed actions preserve the specified prior state.
- Successful and partial outcomes match verified filesystem/database state and link to durable evidence.

## Verification

- Run dedicated Trash browser acceptance twice against disposable roots.
- Run Backend Trash/purge workflow acceptance and UI permission/disclosure regressions.

## Risks or Notes

- UI copy must clearly distinguish Digital Asset Trash, Repair Quarantine, and database Restore.
