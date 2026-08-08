# UI-015 — Add Permission and Disclosure Browser Acceptance

## Task ID

`UI-015` — Status: `Proposed`

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

