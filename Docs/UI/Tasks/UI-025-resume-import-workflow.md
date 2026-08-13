# UI-025 — Resume Import Workflow

## Task ID

`UI-025` — Status: `Complete`

## Title

Make the Import Wizard Explicitly Resumable and Recoverable

## Related Specification(s)

- [UI Specification](../Specification.md), sections 3–5 and 8.
- Backend [Import Workflow](../../Backend/Specifications/Import-Workflow.md).

## Goal

Preserve a Writer's composed batch and reviewed choices across interruption,
while respecting Preview expiry, replay protection, and filesystem safety.

## Scope

- Browser-owned Import compose draft, action, items, reviewed selection, and safe result reference.
- Stable Import resume/restart entry and explicit abandon action.
- Revalidation of a restored Preview or generation of a fresh Preview when the prior identity expired or became stale.
- Recovery from navigation, refresh, browser restart, Backend restart, network failure, and delayed confirmation.

## Workflow Contract

- Entry and preconditions: Writer enters **Import Albums** with configured source/archive roots.
- States and next actions: composing, previewing, reviewable, confirming, executing, succeeded/partial/NeedsRepair/failed, expired/stale, abandoned.
- Persistence and recovery: compose and selections survive safe interruptions; Preview Token is validated before reuse; execution results resume through the durable Operation when available.
- Completion evidence: per-item durable outcome plus Operation link; NeedsRepair links to its next workflow.
- Failure safety: no automatic execution on restore; stale/replayed Preview requires re-preview and retains the source batch where safe.

## Out of Scope

- Resuming a partially transmitted file copy independently of Backend workflow support.
- Sharing a draft across browser profiles.

## Dependencies

- BT-019, BT-026, BT-036 and UI-013 acceptance fixtures.

## Implementation Steps

1. Define the Import draft schema, expiry, sensitive path handling, and explicit removal rules.
2. Restore or safely re-preview interrupted batches from a stable Import entry.
3. Connect durable execution results to Operation/Issue recovery rather than memory-only results.
4. Add interruption and Backend-restart browser scenarios for COPY, MOVE, and database-only modes.

## Acceptance Criteria

- Refresh/navigation/browser restart does not silently erase a composed batch.
- A restored workflow never executes without a fresh explicit confirmation.
- Expired, stale, or replayed Preview reports why it cannot continue and offers re-preview without unnecessary re-entry.
- Completed/partial results remain discoverable through durable evidence after refresh.
- Explicit Abandon clears the local draft without mutating database or filesystem state.

## Verification

- Extended UI-013 real-browser scenarios and Backend Import workflow regression.
- Durable database/filesystem assertions for cancellation, stale, replay, and partial failure.

## Risks or Notes

- Source paths are operationally sensitive. Draft storage must be local-only,
  bounded, documented, and excluded from diagnostics.

## Completion Record

- Import now persists compose, selection, Preview, confirmation, results, and
  Operation reference, restores them after interruption, and supports explicit Abandon.
