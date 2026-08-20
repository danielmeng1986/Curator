# BT-035 — Implement Digital Asset Trash Purge

## Task ID

`BT-035` — Status: `Ready`

## Title

Implement Administrator-Confirmed Permanent Digital Asset Purge

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- [Operation Logging](../Specifications/Operation-Logging.md).
- [Authentication](../Specifications/Authentication.md).

## Goal

Implement the final, explicitly destructive removal of eligible assets from Digital Asset Trash while preserving the evidence required to explain what was removed and any failed or partial outcome.

“Permanent” applies only to the digital assets. Album, Photo, relationship, AI
Work, Review, Operation, and public-identifier database evidence is retained.

## Scope

- Purge eligibility/readiness preview with stable identity/version.
- Admin-only individual and reviewed batch purge.
- Retention and hold enforcement, filesystem deletion, lifecycle finalization
  to `asset_state = DELETED`, and verification.
- Retained tombstone metadata including deletion time/actor/Operation, reviewed
  Photo count and byte total, safe historical logical path, and manifest digest.
- Idempotency, replay/stale protection, Operation evidence, and Issue/Repair hand-off.

## Out of Scope

- Moving active assets into Trash or restoring them, owned by `BT-034`.
- Repair Quarantine retention cleanup and database Snapshot cleanup.
- Web UI, owned by `UI-010E`.
- Physical deletion of catalog, Photo, relationship, AI Work, Review, or
  Operation rows.

## Dependencies

- `BT-033` and `BT-034` — supply the approved normative contract and
  recoverable Trash lifecycle.
- `BT-012`, `BT-013`, and `BT-015` — Operation, Admin authorization, and failure escalation.

## Implementation Steps

1. Implement purge eligibility and impact preview read models. Eligibility
   requires Trash state, completed retention, no hold, no unfinished workflow,
   and no active Operation/Issue/Repair ownership.
2. Implement protected individual and batch purge with version and hold checks.
3. Delete only Backend-resolved assets below configured Trash roots; verify the
   filesystem result before finalizing `asset_state = DELETED` and
   `assets_available = false`.
4. Preserve catalog identities and material historical evidence, and redact or
   label paths so deleted assets cannot be presented as openable resources.
5. Route partial or unverifiable results to `NEEDS_REPAIR` without physically
   deleting database evidence or claiming success.
6. Add destructive-path acceptance using disposable roots only.

## Acceptance Criteria

- Only eligible Trash items can be purged, and only an Admin can authorize the action.
- Purge never deletes Album or Photo database rows and never changes the
  Album's business `status_id`.
- Successful purge leaves the same public identities and historical links
  queryable with `asset_state = DELETED` and no asset-open action.
- Confirmation identifies Album/Photo scope and consequences without unnecessary absolute-path disclosure.
- Hold, retention, stale, replay, missing-file, and collision rules produce specified outcomes without deleting unrelated assets.
- Successful purge is verified; partial failure is truthful and linked to recoverable Issue/Repair evidence.
- Tests never target a production-like archive, Trash, Quarantine, or database path.

## Verification

- Run purge workflows twice on isolated disposable roots.
- Run authorization, Operation, Issue/Repair, Trash, and complete Backend regression suites.

## Risks or Notes

- This task is intentionally separate from recoverable Trash because permanent deletion requires a stronger review and test boundary.
- “Database-only deletion” is not a purge mode. If catalog unregistration is
  ever required, it needs a separately named and specified lifecycle action
  that still preserves historical identity.
