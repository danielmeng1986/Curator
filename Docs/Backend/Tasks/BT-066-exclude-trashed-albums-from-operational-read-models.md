# BT-066 — Exclude Trashed Albums from Operational Read Models

## Task ID

`BT-066` — Status: `Complete`

## Title

Enforce Active-Album Boundaries Across Operational Read Models and Writes

## Related Specification(s)

- [Digital Asset Trash](../Specifications/Digital-Asset-Trash.md), especially
  the active-library read-model and retained-history rules.
- [API Specification](../Specifications/API-Specification.md), Album lifecycle
  collection, selector, editable-detail, and Work Dispatch contracts.
- [Repository Specification](../Specifications/Repository-Specification.md),
  canonical `AlbumListReadModel` and Trash/history projections.
- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md),
  candidate selection from the normal Album collection.

## Goal

Ensure `catalog_state = TRASHED` Albums cannot appear in or participate in any
normal current-business projection, selector, candidate set, or mutation,
while preserving their relationships and completed workflow evidence in
explicit Admin Trash and historical/audit projections.

## Scope

- Centralize or consistently apply the `catalog_state = ACTIVE` predicate to
  ordinary Album collection, search, count, selector, editable-detail, and
  association read models.
- Exclude Trashed Albums from Model-detail and Studio-detail Album lists and
  from an Active Album's ordinary related-release presentation.
- Exclude Trashed Albums from Status Album counts intended to describe the
  normal catalog. Retain referential counts used for deletion protection.
- Reject Trashed Albums supplied through explicit IDs to Album batch mutation,
  relationship creation/update, Work Dispatch Preview/execute, and equivalent
  current-work entry points.
- Preserve the existing Work Dispatch Available behavior and add direct
  regression evidence that its candidate query and count exclude Trashed
  Albums under every availability/filter combination.
- Defensively exclude Trashed Albums from current Dispatch Active, Review, and
  Closure projections. A lifecycle inconsistency must remain diagnosable via
  Operation/Issue evidence rather than becoming actionable current work.
- Include `catalog_state` and `asset_state` where an explicit historical
  projection needs to explain retained Album identity after Trash or purge.

## Out of Scope

- Removing Album, Photo, relationship, Work, Review, or Operation database
  records. Those records remain permanent historical evidence.
- Filtering Trashed Albums out of Administrator Trash, deleted-asset history,
  Dispatch History, Review History, Operation History, Issue, Repair, or other
  explicitly historical/audit projections.
- Treating a Trashed Album path as reusable during Import. Restore and canonical
  path collision rules continue to reserve or report that path as specified.
- Changing Album `status_id`, Trash/Restore behavior, retention, hold, or purge.
- UI presentation beyond consuming corrected Backend read models and stable
  validation errors.

## Dependencies

- `BT-033` — supplies the approved lifecycle and active-versus-history rules.
- `BT-034` — supplies `catalog_state`, `asset_state`, Trash/Restore, and normal
  Album collection filtering. This dependency is complete.
- `BT-055` and `BT-056` — supply candidate Preview and atomic Dispatch execution
  boundaries that require explicit-ID lifecycle revalidation.
- `UI-037` — supplies a verified way to create a recoverable Trashed Album from
  the normal application. This dependency is complete.

## Implementation Steps

1. Inventory every repository query and service mutation that reads or accepts
   a permanent Album, and classify it as normal operational, Trash Admin, or
   historical/audit.
2. Introduce a shared repository predicate/helper where it reduces drift, and
   apply Active filtering to normal counts, association lists, selectors, and
   current workflow projections.
3. Separate visibility from referential integrity: keep all-row reference
   checks used to protect Status/Studio/Model/relationship deletion, while
   normal display counts include Active Albums only.
4. Add Backend lifecycle validation for explicit Album IDs used by batch edit,
   relationship mutation, Dispatch Preview, and Dispatch execute. Return a
   stable `ALBUM_NOT_ACTIVE` or workflow-specific stale/conflict response with
   zero mutation.
5. Revalidate Dispatch Albums atomically during execute using lifecycle state
   in addition to UUID/version/reservation checks; never rely only on their
   earlier absence from the Available UI.
6. Add repository, service, real-HTTP API, and disposable workflow tests with
   Active and Trashed Albums sharing Status, Studio, Model, relationships, and
   completed Work history.

## Acceptance Criteria

- `GET /api/v1/work-dispatch/candidates?availability=available` never returns or
  counts a Trashed Album, including with Status, Studio, Model, pagination, and
  alternate Worker-kind filters.
- Available, reserved, and `all` candidate modes are still normal operational
  projections and exclude Trashed Albums.
- A Trashed Album does not appear in ordinary Album search/detail, Model Album
  associations, Studio Album associations, Status normal Album counts,
  related-release selectors, or an Active Album's ordinary relation list.
- Batch edit, relationship mutation, explicit-ID Dispatch Preview, and stale
  Dispatch execute reject a Trashed Album with zero Album, relationship, Work,
  reservation, Operation-success, or filesystem mutation.
- Restoring the same Album to `catalog_state = ACTIVE` makes it eligible for
  normal projections again, subject to all existing business filters and Work
  eligibility rules.
- Dispatch History, completed Review/Promotion history, Operations, Issues,
  Repairs, retained relationships, and Admin Trash continue to resolve the same
  Album identity after Trash.
- Historical views never present a Trashed/Deleted Album as currently editable,
  dispatchable, or asset-available; lifecycle state is explicit where needed.
- Import/path collision protection continues to account for the retained
  Trashed Album and recoverable asset destination.

## Verification

- Repository tests cover Model, Studio, Status, Album relation, selector, and
  count projections with one Active and one Trashed Album.
- Service/API tests cover explicit batch, relationship, Dispatch Preview, and
  preview-then-Trash-then-execute rejection with zero write.
- Work Dispatch browser/API acceptance confirms Available pagination totals do
  not include Trashed Albums and restored Albums re-enter normally.
- Digital Asset Trash/Restore, entity management, Work Dispatch, AI Review,
  Operation/Issue/Repair, Import collision, and complete Backend regressions
  pass.

## Risks or Notes

- Do not implement this as a global SQL view that also hides history; the
  active-versus-historical classification is part of each read-model contract.
- Count semantics require care. A normal display count excludes Trashed Albums,
  but a referential-integrity check must still count retained rows.
- Trash readiness currently prevents Albums with unfinished Work from moving to
  Trash. The additional current-work filters are defense in depth and protect
  against stale previews, direct requests, migration inconsistencies, and future
  workflow extensions.

## Completion Record

- Normal Status counts, Model/Studio Album associations, Album related-release
  lists and relationship targets now include only Active Albums; retained rows
  still participate in referential-integrity protection and historical storage.
- Album batch Preview/update, entity/association mutation routes, explicit-ID
  Dispatch Preview, Preview validation, and atomic Dispatch execution now
  revalidate Active lifecycle state and reject `ALBUM_NOT_ACTIVE` or stale state
  before creating successful Operations, reservations, Groups, or Work Items.
- Dispatch candidate `available`, `reserved`, and `all` modes continue to derive
  from the normal Active Album collection. Current Active/Review/Closure Group
  and Review Queue projections exclude Trashed Albums, while Dispatch History
  and direct historical Review detail retain Album identity with explicit
  catalog/asset lifecycle state.
- Added regression coverage for filtered counts and associations, retained
  relationship rows, all candidate modes and totals, Restore re-entry,
  explicit-ID rejection, preview-then-Trash execution rejection, current Group
  exclusion, historical Group retention, and real HTTP bypass attempts.
- Updated the existing Work Dispatch pagination browser acceptance to scope its
  duplicated top/bottom pagination controls explicitly.
- Verification completed 2026-08-21: 793 Backend tests, seven Web contract
  suites, and the UI-032, UI-011F, UI-037, and UI-005 real-browser workflows
  pass.
