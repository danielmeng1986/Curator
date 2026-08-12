# UI-019 — Request Device Access in the Web Client

## Task ID

`UI-019` — Status: `Complete`

## Title

Add Reader and Writer Device Access Request UI

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), registration request and Token handling.
- [UI Foundation](../01_Foundation_and_Navigation.md), connection and unauthenticated states.

## Goal

Let a new Safari, Chrome, or other supported browser profile request Reader or Writer access, wait for an Administrator decision, and connect automatically without developer tools, terminal commands, JSON, `curl`, or cross-browser Token copying.

## Scope

- Add **Request device access** to the disconnected connection experience.
- Automatically create/reuse the browser profile's stable device identity.
- Collect device name, requested Reader/Writer role, and Registration Proof with clear credential distinctions.
- Generate the candidate Device Token and enrollment proof locally with Web Crypto; persist them only in the requesting browser profile.
- Submit once, render Pending/Approved/Rejected/Expired states, and poll with bounded backoff while the page is open.
- On approval, validate the local Token and transition atomically to the normal connected experience.
- Support safe cancel/retry and page/browser restart without duplicate registrations.

## Out of Scope

- Admin creation/rotation of Registration Proof.
- Admin approval UI.
- Admin-role self-registration, automatic approval, or hardware-backed device identity.

## Dependencies

- `BT-061` — client-owned Token enrollment and protected status contract.
- `UI-002`, `UI-003`, and `UI-004C` — shared feedback, browser fixtures, and connection lifecycle.

## Implementation Steps

1. Define disconnected request, pending, rejection, expiry, cancellation, and successful connection states.
2. Add Web Crypto generation and safe browser-profile persistence for Token/enrollment material.
3. Integrate registration/status endpoints and atomic transition into existing connection storage.
4. Add accessibility, redaction, restart, retry, and multi-browser acceptance coverage.

## Acceptance Criteria

- A user can request Reader or Writer access entirely in the Web UI with no terminal or developer console.
- Device identity is automatic and stable for the requesting browser profile; a different Chrome/Safari profile receives a different identity.
- Registration Proof and candidate Token never appear in the DOM after submission, URLs, logs, errors, analytics, screenshots produced by tests, or diagnostic attachments.
- Refresh or browser restart resumes the same pending request without creating a duplicate.
- Approval causes the original browser profile to validate and connect with the approved role; another browser cannot claim it using visible registration metadata.
- Rejection, expiry, cancellation, network failure, or invalid proof provides a safe retry path and never overwrites an existing valid connection.
- Admin role cannot be requested from this ordinary access UI.

## Verification

- Client tests for local state transitions, Web Crypto material handling, and redaction.
- Real-browser Safari-compatible/Chromium scenarios using disposable registration fixtures.
- Backend enrollment workflow tests and the UI readiness gate.

## Risks or Notes

- Never render the locally generated Token to obtain convenience; automatic storage still treats it as a credential.
- Polling must stop on navigation, terminal state, or cancellation and use bounded backoff.

## Completion Record

- Added **Request device access**, local Web Crypto Token/enrollment generation, persistent pending state, explicit status check, and automatic approved connection.
