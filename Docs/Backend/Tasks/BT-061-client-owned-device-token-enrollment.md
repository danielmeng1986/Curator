# BT-061 — Add Client-Owned Device Token Enrollment

## Task ID

`BT-061` — Status: `Complete`

## Title

Activate Client-Generated Device Tokens After Administrator Approval

## Related Specification(s)

- [Authentication](../Specifications/Authentication.md), registration, approval, Token issuance, storage, and renewal.
- [API Contract](../Specifications/API-Contract.md), public registration and authenticated Admin decision routes.

## Goal

Let a requesting browser retain its own one-time Device Token locally and become connected after Administrator approval, without copying Token plaintext from the Admin browser or storing retrievable plaintext in the Backend.

## Scope

- Accept a cryptographically random client-generated Token hash and enrollment proof with a registration request.
- Bind the pending request to device identity, requested role/scopes, Token hash, and a single requesting browser profile.
- On Admin approval, atomically activate the submitted Token hash with approved role/scopes.
- Expose a minimal status endpoint that lets only the requesting browser distinguish Pending, Approved, Rejected, Expired, and Consumed enrollment states.
- Add expiry, replay prevention, cancellation, replacement, audit evidence, and cleanup for abandoned enrollments.
- Preserve hash-only Backend Token storage and existing authentication enforcement.

## Out of Scope

- Registration Proof generation and management.
- Web forms, polling screens, or Admin UI changes.
- Hardware-backed keys, browser fingerprinting, WebAuthn, or cross-device Token recovery.

## Dependencies

- `BT-013` and `BT-040` — current registration, approval, Token, and Admin safety contracts.
- Authentication and API Contract amendments must approve client-generated Token activation, enrollment-proof semantics, expiry, and status disclosure before this task becomes `Ready`.

## Implementation Steps

1. Specify client Token entropy/encoding, hash submission, enrollment proof, expiry, status disclosure, and replay rules.
2. Add persistence/repository support for pending client-owned enrollment without storing Token plaintext.
3. Adapt registration approval to atomically activate the pending hash and return safe metadata rather than Token plaintext for this flow.
4. Add status, cancellation, expiry cleanup, compatibility, and end-to-end authentication tests.

## Acceptance Criteria

- The requesting browser generates and retains Token plaintext; Backend persistence contains only its approved hash.
- Possession of registration UUID, device identity, or public status URL alone cannot claim, replace, or authenticate the Token.
- Before approval the candidate Token cannot authenticate; after approval it authenticates only with the approved role/scopes.
- Rejection, expiry, cancellation, tampering, or replay never activates a Token.
- Admin approval never displays or receives client Token plaintext and cannot exceed requested role/scopes.
- Status responses reveal no Token, Token hash, Registration Proof, Admin identity, or unrelated registrations.
- Existing server-issued Tokens and renewal behavior remain compatible until explicitly migrated.

## Verification

- Service/repository tests for pending, approved, rejected, expired, cancelled, tampered, and replayed enrollments.
- API workflow tests proving pre-approval denial and post-approval authentication.
- Redaction inspection plus the complete Backend regression suite.

## Risks or Notes

- A plain registration UUID is not an adequate enrollment capability; use an independent high-entropy proof stored only in the requesting browser.
- Browser local storage is not hardware protection. XSS and browser-profile compromise remain credential-compromise risks.

## Completion Record

- Added browser-generated Token hash/enrollment proof persistence, proof-protected status, pre-approval denial, atomic approval activation, expiry, and Admin read-model redaction.
- Preserved legacy server-issued registration compatibility and existing Token/renewal enforcement.
