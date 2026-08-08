# UI-004B — Add Loopback Administrator UI Bootstrap

## Task ID

`UI-004B` — Status: `Complete`

## Title

Add One-Time Loopback Administrator UI Bootstrap

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), trusted-LAN and one-time issuance rules.
- [UI Foundation](../01_Foundation_and_Navigation.md) and [UI Safety](../06_Safety_and_Acceptance.md).

## Goal

Allow an operator who controls both the server console and a loopback browser
to initialize the first administrator without enabling anonymous self-approval.

## Scope

- Console generation of a short-lived, single-use bootstrap code.
- Loopback-only bootstrap-status and completion endpoints.
- UI collection of code, device name, and stable browser-device identity.
- One-time Token display, immediate local storage, acknowledgement, audit, rate limiting, and permanent closure after initialization.

## Out of Scope

- LAN bootstrap, automatic approval, accounts/passwords, or anonymous admin reset.
- Re-display of an issued Token.

## Dependencies

- UI-004A — establishes the console trust anchor and recovery path.
- UI-002 — shared safe errors and secret-handling feedback.
- Approved Authentication/Architecture decision for bootstrap-code lifecycle.

## Implementation Steps

1. Specify zero-admin detection, code hashing/expiry/use, loopback checks, rate limits, and audit outcomes.
2. Implement Backend bootstrap endpoints and the first-run UI.
3. Add browser tests for success, expiry, wrong code, replay, non-loopback, existing-admin, and interrupted acknowledgement.

## Acceptance Criteria

- Loopback origin alone never authorizes initialization; a valid console-issued code is required.
- The code expires, is single-use, is not logged in plaintext, and becomes unusable once an Admin exists.
- Token plaintext is disclosed only in the issuance response and is never retrievable.
- All rejected attempts preserve authentication state; security-relevant outcomes are audited without secrets.

## Verification

- Run focused Backend security tests and Playwright bootstrap scenarios.
- Verify captured browser artifacts and logs contain neither code nor Token.

## Risks or Notes

- Current loopback approval routes must be reviewed so this flow does not coexist with a weaker unauthenticated approval path.

## Completion Record

- Added a console command that creates a hash-only, ten-minute, single-use UI
  Bootstrap Code; a new Code invalidates the previous one and five failures
  lock it.
- Added loopback-only status/completion endpoints and a first-run UI that saves
  the issued Admin Token before requiring one-time disclosure acknowledgement.
- Retired unauthenticated loopback registration approval; approval now requires
  an authenticated Admin request through `/api/v1`.
- Migrated disposable browser fixtures to establish an Admin through the local
  console trust boundary before approving Reader/Writer devices.
