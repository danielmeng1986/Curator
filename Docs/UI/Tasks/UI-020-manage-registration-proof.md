# UI-020 — Manage Registration Proof in Administrator Center

## Task ID

`UI-020` — Status: `Complete`

## Title

Add Registration Proof Management to Administrator Center

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), authenticated Admin management and registration policy.
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md), credential disclosure and high-risk confirmation.

## Goal

Let an authenticated Administrator enable ordinary device enrollment by generating, rotating, or disabling the Registration Proof entirely in the UI while preserving one-time disclosure and least exposure.

## Scope

- Add a **Registration access** section to **Administrator Center → Devices and Tokens**.
- Show only safe metadata: configured/disabled state, creation/rotation time, last use, and active status.
- Generate a strong Registration Proof through Backend cryptographic generation and display plaintext once.
- Require explicit acknowledgement that the one-time value has been stored.
- Rotate or disable with clear impact review and high-risk confirmation.
- Explain that Registration Proof permits a request only, is not an Admin/Device Token, and does not affect existing approved Tokens.

## Out of Scope

- Reader/Writer request form and pending-browser experience.
- Displaying existing proof plaintext/hash or exporting secrets in reports.
- Network exposure changes or automatic approval.

## Dependencies

- `BT-060` — managed proof lifecycle, safe metadata, rotation, and disablement APIs.
- `UI-010A` — existing Devices and Tokens administration surface.

## Implementation Steps

1. Add safe proof-state presentation and explanatory copy to Devices and Tokens.
2. Add one-time generation modal with storage acknowledgement.
3. Add reviewed rotation/disablement actions and refresh behavior.
4. Add Admin/Writer/Reader authorization, one-time disclosure, redaction, and replay tests.

## Acceptance Criteria

- Only an authenticated Admin can see or operate Registration Proof management.
- Generate/rotate displays plaintext exactly once; refresh and later reads show metadata only.
- Rotation/disablement states impact before execution and never invalidates existing approved Device Tokens.
- Writer, Reader, direct unauthenticated routes, and stale/replayed actions are rejected without side effects.
- UI copy clearly distinguishes Registration Proof, Bootstrap Code, Admin Token, and Device Token.
- Proof plaintext/hash is absent from page history, URLs, logs, test artifacts, and subsequent DOM/read models.

## Verification

- Admin UI component/contract tests for each lifecycle state.
- Playwright browser acceptance covering one-time display, refresh disappearance, rotation, disablement, and role denial.
- Backend authentication regression and UI readiness gate.

## Risks or Notes

- Clipboard use remains a user-controlled disclosure boundary; provide copy support without reading clipboard contents back.

## Completion Record

- Added **Registration access** state, one-time Proof generation/rotation display, disablement, impact confirmation, and safe metadata to **Devices and Tokens**.
