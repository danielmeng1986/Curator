# UI-010A — Administer Devices and Tokens

## Task ID

`UI-010A` — Status: `Proposed`

## Title

Add Device Registration and Token Administration

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), registration, approval, renewal, role elevation, and revocation.

## Goal

Let an authenticated Admin review device requests and manage Token lifecycle
without exposing stored secrets or allowing loss of the last usable Admin.

## Scope

- Pending registrations; approve/reject with role/scope reduction.
- Active, expiring, expired, replaced, and revoked Token metadata.
- Renewal and role-elevation review; Token revocation.
- Last-usable-Admin protection and security Operation links.

## Out of Scope

- First-admin bootstrap, handled by UI-004A/B.
- Retrieving or re-displaying Token plaintext.

## Dependencies

- UI-010 and complete authenticated management APIs.
- Authentication specification decision for last-Admin protection and role-elevation lifecycle.

## Implementation Steps

1. Define Admin-safe registration/token list and action contracts.
2. Enforce approval, scope, revocation, and last-Admin rules in Backend services before adding UI actions.
3. Build management views and test all lifecycle/rejection paths.

## Acceptance Criteria

- Registration proof permits consideration only; it never grants access or self-approval.
- Admin can reduce but cannot silently exceed the requested/allowed authorization without the specified elevation workflow.
- No API or UI retrieves token hash/plaintext after issuance.
- Revoking the last usable Admin Token is rejected with zero side effect and a clear recovery explanation.

## Verification

- Run authentication service/API tests and UI-010D browser scenarios.
- Inspect logs and artifacts for Token/registration-secret redaction.

## Risks or Notes

- Existing loopback-only unauthenticated approval behavior must be retired or narrowed when authenticated administration becomes available.

