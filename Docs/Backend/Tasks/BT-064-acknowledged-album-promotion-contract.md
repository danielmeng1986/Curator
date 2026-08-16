# BT-064 — Acknowledged Album Promotion Contract

## Task ID

`BT-064` — Status: `Complete`

## Title

Replace Repeated Album-Name Entry with Bound Promotion Acknowledgement

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md),
  Album-name Promotion policy.
- [API Specification](../Specifications/API-Specification.md), AI Review and
  Promotion endpoints.
- [UI Specification](../../UI/Specification.md), safe confirmation.
- `BT-051` and `UI-033`.

## Goal

Allow an Administrator to execute a reviewed single-Album Promotion by
explicitly acknowledging the displayed change, without retyping the already
approved selected name, while preserving every authoritative Backend safety and
audit boundary.

## Scope

- Replace Promotion Preview's exact confirmation text with an explicit
  acknowledgement-required indicator.
- Require the execute request to contain the literal boolean
  `acknowledged: true`.
- Preserve signed expiring Admin ownership, review/Album/Workspace version
  binding, uniqueness, one-winner, Snapshot, Operation, idempotency, stale, and
  failure-evidence behavior.
- Amend controlling specifications before completing implementation.
- Update Backend service, HTTP adapter, API/workflow acceptance, and affected
  first-party client tests.

## Out of Scope

- Bulk or automatic Promotion.
- Combining Review approval and Promotion into one Backend transaction.
- Relaxing Preview, stale-state, authorization, Snapshot, uniqueness, or audit
  requirements.
- Database migration or stored Promotion-history changes.
- Frontend next-review navigation or Dispatch progress polling; those remain in
  `UI-033`.

## Dependencies

- `BT-051` — existing unique signed Album-name Promotion.
- `UI-026` — reviewed action lifecycle.

## Contract Decisions

1. Preview returns `acknowledgement_required: true` and the authoritative
   current/resulting name and Status values.
2. Execute accepts only the signed Preview token plus the JSON boolean
   `acknowledged: true`; strings, numbers, false, null, and omission are invalid.
3. Acknowledgement proves review of the Preview, not target-name authority. The
   signed token and fresh Backend state remain the authority for the result.
4. Rejected acknowledgement has zero Promotion, Album, Status, Operation, and
   Snapshot side effects.
5. Successful and idempotent replay behavior remains controlled by the signed
   Preview identity and repository transaction.

## Implementation Steps

1. Amend the Work Dispatch, API, and UI confirmation specifications.
2. Change Promotion Preview and execute service/HTTP contracts.
3. Update first-party callers and focused service/API/workflow tests.
4. Run Promotion, AI Workspace, and API regression suites.

## Acceptance Criteria

- Preview discloses current/resulting name and Status and requires explicit
  acknowledgement without returning confirmation text to retype.
- Only the literal JSON boolean `true` can execute an otherwise valid Preview.
- Missing, false, or malformed acknowledgement causes no durable or Snapshot
  side effect.
- Cross-Admin, expired, stale, replay, uniqueness, competing-winner, required
  Snapshot, failure-audit, and authorization behavior remains intact.
- Existing Promotion history and stored evidence remain readable without a
  migration.

## Verification

- `apps/backend/tests/test_services.py` Promotion contract cases.
- `apps/backend/tests/test_api_contract.py` real HTTP contract journey.
- `apps/backend/tests/test_ai_workspace_workflow_acceptance.py` complete
  Workspace workflow.
- Affected Web contract/browser fixtures followed by the full UI-033 journey.

## Risks or Notes

- This is a confirmation-mechanism change, not a risk-classification change.
  Album Promotion remains a deliberate, previewed, one-Album material action.

## Completion Record

- Amended the Work Dispatch, API, UI confirmation, and AI Collection Workspace
  specifications to make acknowledgement the controlling contract.
- Promotion Preview now returns `acknowledgement_required: true` without exact
  confirmation text; execute requires the literal boolean `acknowledged: true`.
- Updated the service, HTTP adapter, first-party Web confirmation, and affected
  service/API/Workspace/browser tests while retaining all existing signed-token,
  stale, Snapshot, winner, Operation, failure-audit, and idempotency behavior.
- Completed on 2026-08-16; focused service and Workspace tests, 16 real-HTTP API
  cases, the UI contract test, and both AI Review/Promotion browser journeys
  passed.
