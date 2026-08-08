# BT-040 — Complete Authentication Administration and Last-Admin Safety Contract

## Task ID

`BT-040` — Status: `Complete`

## Goal

Expose a complete authenticated Admin management contract for registration,
renewal, and Token metadata while preventing removal of the last usable Admin.

## Scope

- Admin-safe registration, renewal, and Token collections/details.
- Registration approve/reject with authorization no broader than requested.
- Renewal approve/reject and one-time replacement Token delivery.
- Active Token revocation with atomic last-usable-Admin protection.
- Role-elevation review, stable errors, Operation evidence, and secret redaction.

## Out of Scope

- First-Admin bootstrap and offline all-Admin-loss recovery.
- Retrieving or redisplaying existing Token plaintext/hash.

## Acceptance Criteria

- Only Admin principals may inspect or mutate authentication administration state.
- Lists contain metadata only and never plaintext, hashes, or registration proof.
- Approval cannot exceed requested role/scopes without an explicit elevation request.
- Revoking the final currently usable Admin Token returns `409` atomically.
- Every accepted/rejected lifecycle decision has truthful durable evidence.

## Verification

- Authentication service/API lifecycle and concurrency tests.
- Complete Backend regression and UI-010A browser acceptance.

## Risks or Notes

- A once-disclosed newly issued Token may be delivered only in the successful
  approval response and must not enter logs, traces, or later reads.

## Completion Record

- Added Admin-safe registration, Token, and renewal state plus approval,
  rejection, renewal, and revocation routes.
- Enforced requested-role/scope ceilings and once-only plaintext delivery.
- Added atomic last-usable-Admin protection under an immediate transaction.
- Added durable lifecycle Operations and authenticated end-to-end coverage for
  elevation rejection, issuance, renewal replacement, revocation, and redaction.
