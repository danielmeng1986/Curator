# BT-041 — Complete Backup and Snapshot Administration Contract

## Task ID

`BT-041` — Status: `Completed`

## Goal

Provide an Admin-only, Backend-discovered recovery-point catalog and preview-
bound creation, verification, and retention cleanup workflow.

## Scope

- Safe recovery-point metadata: identity, reason, tag, time, class, protection,
  eligibility, and verification state without absolute paths.
- Manual creation and explicit verification.
- Signed cleanup preview bound to catalog state and eligible item identities.
- Single-use cleanup execution with partial durable outcomes and Operation links.

## Out of Scope

- Database Restore, owned by BT-042.
- Client-selected files or arbitrary backup deletion.

## Acceptance Criteria

- Only Backend-discovered files under configured roots can be listed or acted on.
- Cleanup removes only reviewed, expired, unprotected eligible items.
- Stale/replayed/cancelled/unauthorized requests have zero cleanup effect.
- Verification and partial cleanup outcomes are reported truthfully.

## Verification

- Disposable backup-root API and filesystem tests, complete Backend regression,
  and UI-010B browser acceptance.

## Implemented

- Admin catalog models use opaque identities and never expose absolute paths.
- Manual creation and SQLite integrity verification operate only on
  Backend-discovered recovery points.
- Cleanup uses a signed, expiring catalog preview and a durable single-use
  claim before deleting only reviewed, expired, unprotected items.
- Creation and cleanup return durable Operation links; cleanup reports partial
  failures without hiding successful deletions.

## Result

- Focused backup administration contract tests: passed.
- Complete Backend regression: 677 tests passed.
- UI acceptance is owned by UI-010B.
