# BT-033 — Specify Digital Asset Trash Lifecycle

## Task ID

`BT-033` — Status: `Ready`

## Title

Specify Album and Photo Trash, Recovery, and Permanent Purge Semantics

## Related Specification(s)

- [Architecture](../../02-Architecture.md), Archive and application responsibilities.
- [Repair Workflow](../Specifications/Repair-Workflow.md), Quarantine safety boundary.
- [Operation Logging](../Specifications/Operation-Logging.md), destructive-operation evidence.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md), pre-action recovery policy.

## Goal

Define one authoritative lifecycle for removing Albums or individual Photos from the active library, recovering them, and permanently purging their digital assets without confusing Trash with Repair Quarantine.

## Scope

- Define Album as the default management and deletion unit in `apps.web`.
- Define Photo-level Trash requests originating from a future native client.
- Specify active, trashed, restored, purge-eligible, purging, purged, and failure/repair states.
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
2. Define Album-level and Photo-level request, preview, recovery, and purge contracts.
3. Resolve filesystem/database atomicity, retention, hold, collision, and `NeedsRepair` behavior.
4. Update Architecture, API, Operation, Repair, and authentication specifications where their guarantees change.
5. Produce an acceptance matrix for `BT-034`, `BT-035`, and `UI-010E`.

## Acceptance Criteria

- Trash, Repair Quarantine, database Snapshot Restore, and permanent purge have distinct names and normative purposes.
- The specification states exactly what happens to files, Album records, Photo records, relationships, and public identifiers at every transition.
- Album deletion includes all contained Photos as one reviewed asset scope; Photo-level deletion does not silently delete its Album.
- Cancelled, unauthorized, stale, repeated, collision, missing-file, and partial-failure outcomes have explicit zero-side-effect or repair semantics.
- Permanent purge requires Admin authorization, explicit impact confirmation, and durable evidence.
- No implementation task remains dependent on an unresolved “Archive is permanent” contradiction.

## Verification

- Review the cross-specification consistency checklist and acceptance matrix.
- Confirm `BT-034`, `BT-035`, and `UI-010E` can be implemented without inventing lifecycle behavior.

## Risks or Notes

- This is a specification task. It must complete before destructive filesystem behavior is added.
