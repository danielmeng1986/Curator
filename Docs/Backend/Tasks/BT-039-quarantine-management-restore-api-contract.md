# BT-039 — Complete Quarantine Management and Restore API Contract

## Task ID

`BT-039` — Status: `Complete`

## Goal

Expose an Admin-only, preview-bound API for intact repair Quarantine moves and
safe restoration without permitting arbitrary filesystem browsing or overwrite.

## Scope

- Admin-only Quarantine list/detail read models with retention, inventory,
  originating Repair, and Operation links.
- Signed, expiring quarantine and restore previews bound to item/path state,
  approved managed-relative destinations, consequence, and eligibility.
- Single-use execution, stale/replay protection, snapshot enforcement, intact
  move verification, and truthful Operation outcomes.
- Structured unauthorized, invalid path, missing source, collision, stale, and
  replay errors with zero unintended mutation.

## Out of Scope

- Digital Asset Trash and permanent asset purge.
- General filesystem browsing or database snapshot restore.

## Dependencies

- BT-020, BT-027, BT-029, BT-030, and BT-038.

## Acceptance Criteria

- Only Admin may inspect or mutate Quarantine state.
- Execution can perform only the exact reviewed source/destination and never overwrite.
- Cancelled or rejected requests preserve both filesystem and durable state.
- Successful quarantine/restore is verified and linked to Repair and Operation evidence.
- UI-facing labels and read models distinguish repair Quarantine from Digital Asset Trash.

## Verification

- Focused API tests and disposable filesystem workflow acceptance.
- Complete Backend regression and UI-009 browser acceptance.

## Risks or Notes

- Absolute configured roots remain server-side; clients receive managed-relative paths only.

## Completion Record

- Added explicit `quarantine_root` configuration and Admin-only list/detail APIs.
- Added signed, expiring, single-use quarantine/restore previews bound to
  Backend-derived paths, recursive directory state, configuration, and durable records.
- Added restoration outcome persistence and Operation links without overwrite.
- Verified zero-write preview, stale/replay/collision rejection, intact move,
  snapshot-protected restore, role denial, and authenticated HTTP execution in
  disposable filesystem roots.
