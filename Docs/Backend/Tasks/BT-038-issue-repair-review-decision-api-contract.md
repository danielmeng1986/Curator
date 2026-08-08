# BT-038 — Complete Issue and Repair Review and Decision API Contract

## Task ID

`BT-038` — Status: `Complete`

## Goal

Expose role-safe Issue and Repair queues, details, and Backend-authorized
decisions so the Web client never infers repair policy or mutates workflow
state directly.

## Scope

- Filterable Issue and Repair read models with links and allowed actions.
- Issue begin/reopen, Admin ownership/resolve/archive decisions.
- Repair confirmation, start, escalation, action completion, verification, and ignore decisions.
- Optimistic `expected_updated_at` checks for stale/repeated decisions.
- Admin-only bounded suppression creation and revocation.
- A truthful Operation for every accepted decision; structured 400/403/404/409 outcomes.

## Out of Scope

- Quarantine and restore, owned by BT-039.
- Arbitrary filesystem commands or client-side classification.

## Dependencies

- BT-027, BT-028, BT-030, and BT-037.

## Acceptance Criteria

- Read models state permitted actions explicitly and retain Issue/Repair/Operation links.
- Role, confirmation, transition, stale, and replay constraints are enforced by Backend.
- Rejected decisions have no workflow or filesystem side effect.
- Accepted decisions produce durable Operation evidence matching the resulting state.
- Sensitive paths and diagnostics are not disclosed outside their authorized role.

## Verification

- Focused authenticated API and service tests for every decision class.
- Repair-policy, repair-decision, and traceability workflow acceptance.
- Complete Backend regression and UI-008 browser acceptance.

## Risks or Notes

- `expected_updated_at` is an optimistic workflow version, not a client-editable timestamp.

## Completion Record

- Added role-safe Issue/Repair queues and details with Backend-computed actions.
- Added optimistic Issue and Repair decisions and linked Operation evidence.
- Added Admin-only bounded suppression API with path, expiry, and role validation.
- Added additive Repair schema compatibility and authenticated API coverage for
  review, redaction, confirmation, transitions, stale replay, role boundaries,
  and suppression.
