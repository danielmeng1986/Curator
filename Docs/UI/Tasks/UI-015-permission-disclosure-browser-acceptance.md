# UI-015 — Add Permission and Disclosure Browser Acceptance

## Task ID

`UI-015` — Status: `Complete`

## Title

Add Role and Diagnostic Disclosure Browser Acceptance

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md).
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md), role-sensitive disclosure.
- [API Contract](../../Backend/Specifications/API-Contract.md).

## Goal

Prove that Reader, Writer, Admin, and invalid credentials receive only their
allowed UI capabilities and diagnostic fields, including direct-request attacks.

## Scope

- Missing, malformed, invalid, expired, revoked, and insufficient-scope Tokens.
- Reader/Writer/Admin navigation, visible actions, direct URLs, and direct protected requests.
- Operation/Issue/Repair/admin diagnostic disclosure and redaction.
- Authentication failure side-effect assertions and reconnection behavior.

## Out of Scope

- Penetration testing, HTTPS deployment certification, or browser-storage hardening beyond the current model.

## Dependencies

- UI-002, UI-003, UI-004C, UI-007, and all role-sensitive feature surfaces.

## Implementation Steps

1. Build a role-to-route/action/field expectation table from UI-001.
2. Implement browser and API-interception scenarios for allowed and forbidden access.
3. Scan rendered content and retained artifacts for prohibited fields/secrets.

## Acceptance Criteria

- UI visibility and Backend enforcement agree for every mapped role/action.
- Direct URL or crafted request cannot bypass authorization.
- Reader never receives sensitive recovery diagnostics; no role receives plaintext stored credentials.
- Every rejected protected action has zero business side effect.

## Verification

- Run browser disclosure suite twice and Backend authentication/Operation disclosure tests.

## Risks or Notes

- Absence from rendered HTML is insufficient if the sensitive field was already delivered in an API response; network payloads must also be checked.

## Completion Record

- Added isolated Reader, Writer, and Admin browser contexts so device Tokens and
  role state cannot leak between acceptance scenarios.
- Proved missing, malformed, invalid, expired, revoked, and insufficient-scope
  credentials through direct protected requests with zero Album, Status,
  Quarantine, or Backup side effects and successful approved reconnection.
- Mapped navigation/action visibility to direct Backend enforcement for entity
  writes, Import, Quarantine, authentication administration, Work Dispatch, and
  AI Review routes.
- Captured Operation, Repair, and Admin-state network payloads and proved Reader
  redaction, Writer operational context, Admin-only candidates, and absence of
  Token hashes, registration proof, stored plaintext Tokens, sensitive error
  details, and private absolute paths.
- Proved unavailable Operation identifiers are labelled without a false detail
  route, while genuinely missing resources return a safe not-found outcome.
- The final browser suite passed twice from clean disposable roots and 30
  Backend authentication, authorization, Operation disclosure, and
  Issue/Repair disclosure tests passed on 2026-08-11.
