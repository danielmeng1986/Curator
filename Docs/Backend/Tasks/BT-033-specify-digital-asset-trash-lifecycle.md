# BT-033 — Specify Digital Asset Trash Lifecycle

## Task ID

`BT-033` — Status: `Complete`

## Title

Specify Album and Photo Trash, Recovery, and Permanent Purge Semantics

## Related Specification(s)

- [Architecture](../../02-Architecture.md), Archive and application responsibilities.
- [Repair Workflow](../Specifications/Repair-Workflow.md), Quarantine safety boundary.
- [Operation Logging](../Specifications/Operation-Logging.md), destructive-operation evidence.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), pre-action recovery policy.

## Goal

Define one authoritative lifecycle for removing Albums or individual Photos from the active library, recovering them, and permanently purging their digital assets without confusing Trash with Repair Quarantine.

Album and Photo database identities are permanent historical evidence. Neither
Trash nor permanent asset purge physically deletes the corresponding catalog
records; they change independent catalog-visibility and digital-asset lifecycle
state while preserving the Album's existing business `status_id`.

## Scope

- Define Album as the default management and deletion unit in `apps.web`.
- Define Photo-level Trash requests originating from a future native client.
- Define three independent dimensions: Album business `status_id`, catalog
  visibility (`ACTIVE`, `TRASHED`), and digital-asset state (`PRESENT`,
  `TRASHED`, `DELETED`, `MISSING`, `NEEDS_REPAIR`).
- Specify Trash, restore, purge eligibility, purging, asset deletion, and
  failure/repair transitions without overwriting Album business status.
- Define authoritative Trash blockers for active Work Dispatch reservation,
  unreleased Group, Pending/Claimed Work Item, unfinished Review/promotion,
  unclosed Workspace, and active Operation/Issue/Repair ownership.
- Define filesystem layout, database identity retention, Album/Photo membership, collision behavior, retention/hold rules, and authorization.
- Define preview/version, confirmation, idempotency, verification, Operation/Issue/Repair linkage, and partial-failure semantics.
- Reconcile permanent purge with the current “Archive is permanent” architecture statement before implementation.

## Out of Scope

- Implementing persistence, filesystem moves, APIs, Web UI, or the native macOS application.
- Reusing Repair Quarantine as a user-facing Trash without an explicit specification decision.

## Dependencies

- `BT-011`, `BT-012`, `BT-013`, `BT-015`, and `BT-029` — snapshot, Operation, authentication, Issue, and Quarantine boundaries to distinguish or reuse safely.
- Product decisions in the macOS application memo are context, not a controlling specification.

## Implementation Steps

1. Add a normative Digital Asset Trash specification and terminology/state diagram.
2. Define the independent `status_id`, `catalog_state`, and `asset_state`
   contract, including legal combinations and transitions.
3. Define one Backend-owned eligibility/readiness model used by both the Album
   page and Administrator Center; include stable blocker codes and affected
   Work/Review/Operation links.
4. Define Album-level and Photo-level preview, Trash, recovery, and asset-purge
   contracts. Specify that Album purge preserves Album, Photo, relationship,
   AI Work, Review, Operation, and public-identifier evidence.
5. Resolve filesystem/database atomicity, retention, hold, collision,
   missing-file, redacted historical-path, and `NeedsRepair` behavior.
6. Update Architecture, API, Operation, Repair, authentication, and read-model
   specifications where their guarantees change.
7. Produce an acceptance matrix for `BT-034`, `BT-035`, and `UI-010E`.

## Acceptance Criteria

- Trash, Repair Quarantine, database Snapshot Restore, and permanent purge have distinct names and normative purposes.
- `status_id` remains the Album's business state and is never used to represent
  Trash or digital-asset availability.
- Normal Album read models include only `catalog_state = ACTIVE`; Admin Trash
  and historical-asset read models expose the other states explicitly.
- The specification states exactly what happens to files, Album records, Photo records, relationships, AI evidence, and public identifiers at every transition.
- Album and Photo rows are never physically deleted by Trash or purge. After
  successful purge they remain queryable as historical evidence with
  `asset_state = DELETED` and `assets_available = false`.
- Album deletion includes all contained Photos as one reviewed asset scope; Photo-level deletion does not silently delete its Album.
- Every Trash preview reports `can_trash` and stable blocker details; any
  unfinished workflow that may read assets or write back to Album makes Trash
  unavailable.
- Cancelled, unauthorized, stale, repeated, collision, missing-file, and partial-failure outcomes have explicit zero-side-effect or repair semantics.
- Permanent purge requires Admin authorization, explicit impact confirmation, and durable evidence.
- No implementation task remains dependent on an unresolved “Archive is permanent” contradiction.

## Verification

- Review the cross-specification consistency checklist and acceptance matrix.
- Confirm `BT-034`, `BT-035`, and `UI-010E` can be implemented without inventing lifecycle behavior.

## Risks or Notes

- This is a specification task. It must complete before destructive filesystem behavior is added.
- The legacy `DELETE /api/v1/albums/:id` hard-delete contract must be formally
  retired or made unavailable before any new UI deletion action is enabled.

## Completion Record

- Added the normative [Digital Asset Trash](../Specifications/Digital-Asset-Trash.md)
  state model, eligibility policy, Preview/Execute contracts, authorization,
  retention/hold, recovery, purge, errors, and cross-stack acceptance matrix.
- Established permanent Album/Photo catalog identity and separated business
  `status_id`, `catalog_state`, and `asset_state`.
- Resolved Archive immutability by defining reviewed Digital Asset Trash as the
  only user-removal exception and clarified that database Snapshots cannot
  recover purged asset bytes.
- Updated Architecture, API, Repository, Operation, Repair, Snapshot,
  Authentication, and UI specifications and navigation/read-model boundaries.
- Defined Writer-authorized eligible Album Trash and Admin-only Trash
  administration, restore, hold, deleted-asset history, and permanent purge.
- Made the legacy Album database-hard-delete route explicitly unsupported.
