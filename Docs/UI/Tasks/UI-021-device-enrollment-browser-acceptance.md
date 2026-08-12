# UI-021 — Add Device Enrollment Browser Acceptance

## Task ID

`UI-021` — Status: `Complete`

## Title

Verify End-to-End Multi-Browser Device Enrollment

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), complete registration, approval, and Token lifecycle.
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md), workflow and credential-redaction acceptance.

## Goal

Prove that an existing Admin browser can enable registration and approve a distinct new browser profile that then connects as Reader or Writer without terminal assistance or secret leakage.

## Scope

- Disposable Admin and requesting-browser contexts with distinct local storage/device identities.
- Admin proof generation, new-browser request, pending state, approval/rejection, and automatic connection.
- Reader and Writer role/scopes, cross-browser isolation, refresh/restart recovery, rotation, disablement, expiry, replay, and denial cases.
- Credential redaction across screenshots, traces, console output, network diagnostics, and failure attachments.

## Out of Scope

- Public Internet deployment, cross-host browser automation, or hardware-backed identity.
- Manual terminal fallback validation except compatibility smoke coverage.

## Dependencies

- `BT-060`, `BT-061`, `UI-019`, and `UI-020` — complete Backend and Web enrollment workflow.
- `UI-017` — reproducible real-browser acceptance infrastructure.

## Implementation Steps

1. Extend disposable fixtures for two isolated browser profiles and managed proof state.
2. Add Writer and Reader happy paths from proof generation through authenticated navigation.
3. Add rejection, expiry, rotation, replay, duplicate, wrong-browser, and disclosure-negative cases.
4. Register the scenarios in the UI and release readiness gates.

## Acceptance Criteria

- A clean Admin browser and clean Chrome-like requester complete enrollment using UI only.
- The requester remains Pending until Admin approval and then connects with exactly approved scopes.
- Safari/Chrome-style browser profiles remain isolated; enrollment material from one cannot authenticate or claim another.
- Refresh and restart preserve safe progress, while rejection/expiry/cancellation terminate it truthfully.
- Rotated/disabled proofs reject new requests without affecting approved Tokens.
- No plaintext Registration Proof, Device Token, Token hash, or enrollment proof appears in retained test artifacts.
- All existing authentication, Admin safety, and browser acceptance suites remain green.

## Verification

- Dedicated Playwright multi-context scenarios for Writer and Reader.
- Automated artifact redaction scan.
- Complete Backend regression, Web browser suite, documentation gate, and release readiness gate.

## Risks or Notes

- Browser-engine parity should be validated manually on Safari if CI supplies only Chromium; behavior must not rely on a Chromium-only API beyond standardized Web Crypto/local storage.

## Completion Record

- Added a disposable two-context Chromium acceptance proving Admin Proof generation, Writer request, Admin approval, requester auto-connect, exact scopes, and secret/hash redaction.
- Registered the workflow in the UI readiness manifest; Safari remains a manual engine-parity check.
