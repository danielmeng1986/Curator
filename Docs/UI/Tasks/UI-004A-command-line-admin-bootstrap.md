# UI-004A — Establish Command-Line Administrator Bootstrap

## Task ID

`UI-004A` — Status: `Complete`

## Title

Establish Supported Command-Line Administrator Bootstrap

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), registration, approval, token handling, and confirmation requirements.
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Replace hand-crafted REST calls with one supported local command that safely
creates the first administrator device and displays its Token exactly once.

## Scope

- Detect whether a trusted Admin has ever been established; expired or revoked
  Tokens do not reopen first-install bootstrap.
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
- Repeating bootstrap after an Admin has been established is rejected with zero authentication-state mutation.
- Partial failure does not leave an approved device without truthful token/audit state.

## Verification

- Run focused authentication CLI tests against disposable databases.
- Run authentication, API-contract, workflow-readiness, and full Backend regression suites.

## Risks or Notes

- Console access is the trust anchor for initial bootstrap and emergency recovery.
- Loss of all Admin Tokens does not reopen bootstrap. The separately specified
  offline recovery command is intentionally not implemented by this task.

## Completion Record

- Added `python3 -m apps.backend auth bootstrap-admin` with explicit device
  name/identity, configured or explicitly selected database, one-time Token
  output, and safe repeated-run refusal.
- Added an atomic repository bootstrap boundary plus compensation when durable
  security Operation recording fails; plaintext is never persisted or logged.
- Amended Authentication Specification to separate first installation from
  loss-of-all-Admin recovery and prohibit automatic or anonymous reset.
