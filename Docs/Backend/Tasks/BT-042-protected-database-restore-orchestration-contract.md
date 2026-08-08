# BT-042 — Complete Protected Database Restore Orchestration Contract

## Task ID

`BT-042` — Status: `Completed`

## Goal

Implement an Admin-only, preview-bound database Restore workflow that preserves
a verified safety snapshot and never claims success before post-Restore health
and Operation persistence are verified.

## Scope

- Select only a verified Backend catalog recovery-point identity.
- Signed, expiring pending-confirmation preview bound to target/catalog/database state.
- Typed confirmation phrase, single-use atomic claim, and duplicate/stale rejection.
- Pre-Restore protective Snapshot creation and verification.
- Restore execution, database integrity verification, durable Operation outcome,
  and explicit failed/interrupted recovery context.
- Response instructing clients to discard cached data and reauthenticate after success.

## Out of Scope

- Arbitrary uploads/paths, filesystem-media Restore, and offline disaster recovery.

## Acceptance Criteria

- No database mutation occurs without a verified target, safety snapshot, and
  exact confirmation bound to a current pending preview.
- Cancelled, invalid, stale, and replayed execution leaves the database unchanged.
- Failure at snapshot, restore, verification, or evidence persistence is truthful
  and retains the best recoverable state.
- Success requires integrity verification and forces UI Token/session revalidation.

## Verification

- Disposable database/backup roots for every stage and failure injection.
- Complete Backend regression and UI-010C/UI-010D browser acceptance run twice.

## Risks or Notes

- In-process SQLite connection replacement requires serialized Restore execution;
  the contract must reject concurrent material writes rather than race them.

## Implemented

- Admin Restore accepts only an opaque, Backend-catalog identity whose latest
  integrity verification passed; arbitrary paths and the old direct rollback
  entry point are rejected.
- A signed ten-minute preview binds the exact target, confirmation phrase, and
  current database state. Durable claims reject replay and are restored after
  database replacement.
- Execution is serialized and requires a verified, protected high-risk safety
  snapshot before database replacement.
- Success requires post-Restore SQLite integrity verification and durable
  Operation persistence, then instructs clients to clear cached state and
  reauthenticate.

## Result

- Focused policy and disposable SQLite Restore tests: passed.
- Complete Backend regression: 682 tests passed.
- UI acceptance is owned by UI-010C and UI-010D.
