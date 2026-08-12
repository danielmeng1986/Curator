# BT-060 — Add Managed Registration Proof Lifecycle

## Task ID

`BT-060` — Status: `Complete`

## Title

Add Administrator-Managed Registration Proof Lifecycle

## Related Specification(s)

- [Authentication](../Specifications/Authentication.md), registration request policy and authenticated Admin management.
- [API Contract](../Specifications/API-Contract.md), authentication-management route boundaries.

## Goal

Allow an authenticated Administrator to generate, rotate, inspect safe metadata for, and disable the Registration Proof through Backend APIs without requiring a terminal or persisting plaintext.

## Scope

- Persist one active Registration Proof hash plus creation, rotation, disablement, and last-use metadata.
- Add Admin-only generate/rotate/disable and safe-state read operations.
- Return newly generated plaintext exactly once and exclude it from later reads, Operations, logs, errors, and backups intended for ordinary inspection.
- Validate public registration requests against the active persisted hash.
- Record truthful security Operations for generation, rotation, use, invalid attempts, and disablement without recording secret material.
- Define a safe migration and compatibility window for `CURATOR_REGISTRATION_SECRET` and `--registration-secret-prompt`.

## Out of Scope

- Device registration-request UI and Admin management UI.
- Registration approval or Device Token activation.
- Username/password accounts, external secret managers, or public-network registration.

## Dependencies

- `BT-040` — authenticated Admin management and secret-redacted read models already exist.
- Authentication and API Contract amendments must decide persisted-proof precedence, environment-variable compatibility, rotation behavior, and whether registration remains loopback-only before this task becomes `Ready`.

## Implementation Steps

1. Amend the Authentication and API Contract specifications with the managed-proof lifecycle and compatibility policy.
2. Add the migration and repository contract for hash-only proof state and metadata.
3. Implement Admin-only lifecycle services/routes and switch registration validation to the active managed proof.
4. Add redaction, replay/rotation, concurrency, migration, and compatibility tests.

## Acceptance Criteria

- Only an authenticated Admin can generate, rotate, disable, or inspect Registration Proof metadata.
- Generation/rotation returns plaintext once; no later API, database read model, Operation, log, or error reveals plaintext or its hash.
- The active proof permits only creation of `PendingApproval`; it never grants access or approval.
- Rotation invalidates the previous proof atomically; disablement causes all new proof-based requests to fail with zero registration side effect.
- Concurrent rotation cannot leave multiple active proofs.
- Existing approved Device Tokens remain valid when a Registration Proof is generated, rotated, or disabled.
- The compatibility behavior for environment-based startup is explicit, tested, and removable in a later task.

## Verification

- Authentication repository/service tests for lifecycle, hashing, rotation, disablement, and concurrency.
- API contract tests for Admin authorization, one-time disclosure, redaction, and invalid-proof zero-write behavior.
- Migration tests and the complete Backend regression suite.

## Risks or Notes

- Persisting plaintext would turn a database disclosure into immediate registration capability and is prohibited.
- A UI-generated proof does not by itself make remote registration safe; the loopback/network boundary remains independently enforced until a Specification changes it.

## Completion Record

- Added migration `0015_ui_device_enrollment`, hash-only singleton proof state, Admin lifecycle APIs, safe metadata, rotation/disablement, audit evidence, and environment fallback compatibility.
- Added service, migration, API, browser, schema-documentation, and redaction verification.
