# UI-004A — Establish Command-Line Administrator Bootstrap

## Task ID

`UI-004A` — Status: `Proposed`

## Title

Establish Supported Command-Line Administrator Bootstrap

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), registration, approval, token handling, and confirmation requirements.
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Replace hand-crafted REST calls with one supported local command that safely
creates the first administrator device and displays its Token exactly once.

## Scope

- Detect whether an active Admin Token already exists.
- Create and approve one local administrator device through Authentication Service boundaries.
- One-time plaintext output, audit Operation, safe retry rejection, and operator guidance.
- A separately explicit recovery mode for loss of all Admin Tokens, if approved by Specification.

## Out of Scope

- Browser bootstrap, normal registration approval, or plaintext Token recovery.
- Resetting authentication automatically when an Admin Token is lost.

## Dependencies

- Authentication Specification amendment defining first-admin bootstrap and recovery authorization.

## Implementation Steps

1. Specify command inputs, first-admin preconditions, output, and recovery policy.
2. Add a Backend CLI command using repositories/services rather than REST scripting or direct SQL.
3. Add first-run, repeated-run, failure, redaction, and audit tests.

## Acceptance Criteria

- The command succeeds only under the specified local bootstrap preconditions.
- Token plaintext is printed once, never persisted or logged, and cannot be retrieved later.
- Repeating bootstrap when a usable Admin exists is rejected with zero authentication-state mutation.
- Partial failure does not leave an approved device without truthful token/audit state.

## Verification

- Run focused authentication CLI tests against disposable databases.
- Run authentication, API-contract, workflow-readiness, and full Backend regression suites.

## Risks or Notes

- Console access is the trust anchor for initial bootstrap and emergency recovery.

