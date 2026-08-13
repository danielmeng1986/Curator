# UI-023 — Correct Permission Disclosure Gate

## Task ID

`UI-023` — Status: `Ready`

## Title

Distinguish Managed Credential Metadata from Plaintext Secret Disclosure

## Related Specification(s)

- [UI Specification](../Specification.md), sections 5 and 8.
- Backend Authentication disclosure contract.

## Goal

Restore the final UI readiness gate without weakening its prohibition on
plaintext credentials, hashes, private paths, or diagnostic secrets.

## Scope

- Define forbidden secret values separately from permitted metadata field names.
- Validate the Admin `registration_proof` state descriptor field-by-field.
- Continue scanning rendered UI and responses for actual fixture credentials,
  proof plaintext, Token hashes, Bootstrap Codes, and private paths.

## Workflow Contract

- Entry and preconditions: automated permission/disclosure suite with isolated Reader, Writer, and Admin browsers.
- States and next actions: pass only after every role response and rendered surface satisfies its disclosure allowlist.
- Persistence and recovery: failure retains sanitized diagnostics and must not stop later suites from being independently runnable.
- Completion evidence: the disclosure suite and complete UI readiness gate pass.
- Failure safety: diagnostic artifacts never retain the secret value that caused a failure.

## Out of Scope

- Renaming the Backend `registration_proof` metadata field.
- Permitting plaintext Registration Proof redisclosure.

## Dependencies

- BT-060 managed Registration Proof lifecycle.

## Implementation Steps

1. Replace field-name substring rejection with schema-aware metadata and value assertions.
2. Add positive state-descriptor coverage and negative injected-plaintext coverage.
3. Run permission/disclosure and complete readiness gates.

## Acceptance Criteria

- Managed state such as enabled/created/rotated/last-used timestamps is permitted.
- Plaintext proof, Device Token, Token hash, Bootstrap Code, private path, and forbidden diagnostics still fail the suite.
- A failure artifact is sanitized and identifies the violated disclosure class.
- All 11 readiness suites can run to completion.

## Verification

- `permission_disclosure_full_browser_acceptance.mjs`.
- `npm run test:ui-readiness`.

## Risks or Notes

- Do not solve this by deleting `registration_proof` from the forbidden list
  without adding value- and schema-aware assertions.
