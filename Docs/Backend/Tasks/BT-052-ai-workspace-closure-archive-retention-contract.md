# BT-052 — Implement AI Workspace Closure, Archive, and Retention Contract

## Task ID

`BT-052` — Status: `Complete`

## Title

Close and Archive AI Workspaces while Preserving Review Evidence

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, lifecycle and retention.
- UI-011B container/Item state separation.
- [Workspace Workflow](../Specifications/Workspace-Workflow.md).

## Goal

Make completed AI Workspaces durably read-only without losing analysis,
evaluation, configuration, Photo Manifest, failure, or Promotion traceability.

## Scope

- Closure preflight for queued, claimed, running, reviewable, approved, failed,
  and unresolved Items plus active Album Reservations/Groups.
- Explicit cancel/retain/block policy for unfinished Items.
- Closed and Archived transitions, archive classification/reason, timestamps,
  Operation links, retention read models, and read-only enforcement.
- Historical behavior when source evidence images are moved, replaced, or missing.

## Out of Scope

- Deleting AI Workspace history or copying all source photos into permanent storage.
- General legal-hold policy.

## Dependencies

- BT-044 through BT-051 and BT-057.
- Approved UI-011A retention duration and unfinished-work closure policy.

## Implementation Steps

1. Define closure preflight/classification and retained evidence model.
2. Implement close/archive commands and system-wide mutation guards.
3. Add unfinished, failed, promoted, missing-evidence, idempotent, and read-only tests.

## Acceptance Criteria

- Closure never silently abandons a running claim or unresolved approved Promotion.
- Closure cannot strand or silently release an Album reservation; every owning
  Group must have a permitted terminal release outcome.
- Closed Workspaces accept no new runs or decisions; Archived Workspaces accept no mutations.
- Missing source images do not erase Manifest metadata or historical conclusions.
- Every close/archive result has an explicit classification and Operation.

## Verification

- Lifecycle matrix and retention read-model tests, failure injection, and full regression.

## Risks or Notes

- Retaining hashes/metadata is not the same as retaining image bytes; UI must
  truthfully distinguish available previews from historical unavailable evidence.

## Completion Record

- Added strict closure preflight: every Group must already have an explicit
  BT-057 release outcome; close never cancels or abandons work implicitly.
- Added `IndefiniteAudit` retention with Completed/Rejected/Cancelled/Abandoned/
  Mixed classification, Admin reasons, timestamps, and atomic Operations.
- Closed and Archived Workspaces reject all active AI workflow mutations while
  retaining complete Item, attempt, result, review, Manifest, and Promotion data.
- Added historical evidence availability states that preserve Manifest metadata
  and conclusions when source images are missing, changed, or unavailable.
