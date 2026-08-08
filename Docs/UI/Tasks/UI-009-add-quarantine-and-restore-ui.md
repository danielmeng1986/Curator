# UI-009 — Add Quarantine and Item Restore UI

## Task ID

`UI-009` — Status: `Complete`

## Title

Add Quarantine and Filesystem Item Restore UI

## Related Specification(s)

- [Repair Workflow](../../Backend/Specifications/Repair-Workflow.md), quarantine and restore safety.
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Provide an Admin-only UI for quarantining and restoring individual filesystem
items with scope preview, confirmation, and verified outcomes.

## Scope

- Candidate/detail evidence, quarantine impact preview, confirmation, item list, restore eligibility, and result.
- Repeated/stale action protection and Operation/Issue links.
- Strict Admin route/action enforcement and safe path disclosure.

## Out of Scope

- Database Snapshot Restore, handled by UI-010C.
- User-initiated Digital Asset Trash, Album/Photo Trash recovery, and permanent purge, handled by UI-010E.
- General filesystem browsing or arbitrary source/destination entry.

## Dependencies

- UI-002, UI-003, UI-007, and UI-010 shell.
- Supported quarantine list/action API contracts; gaps require Backend tasks.

## Implementation Steps

1. Define safe Admin read models and impact/eligibility fields.
2. Implement candidate, quarantine, list, and restore UI states.
3. Test success, cancellation, collision, missing file, replay, and unauthorized access.

## Acceptance Criteria

- The UI cannot choose paths outside Backend-approved roots.
- Confirmation names the affected item and consequence without leaking unnecessary absolute paths.
- Cancelled, unauthorized, invalid, stale, and repeated actions preserve filesystem and durable state.
- A successful action is verified and linked to truthful Operation history.

## Verification

- Run Backend quarantine workflow acceptance with disposable archive roots.
- UI-014 supplies browser/filesystem evidence.

## Risks or Notes

- UI labels must not imply that moving an item to Quarantine repairs the originating Issue automatically.
- Repair Quarantine must never be labelled or presented as Digital Asset Trash; the former isolates repair conflicts, while the latter is a user/admin asset-removal lifecycle.

## Completion Notes

- Added Admin-only Repair Quarantine navigation, list, inventory detail,
  retention state, and Repair/Operation traceability.
- Quarantine begins only from the Backend-provided Repair candidate; restore
  has no editable destination and uses the retained original managed path.
- Both actions require an explicit signed preview confirmation and submit only
  the preview token. Duplicate client execution is suppressed.
- Disposable browser/filesystem acceptance proves Writer denial, zero-write
  preview, intact isolation, inventory, snapshot-protected restore, and durable
  restoration evidence.
