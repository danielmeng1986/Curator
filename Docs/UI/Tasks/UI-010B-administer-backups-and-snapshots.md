# UI-010B — Administer Backups and Snapshots

## Task ID

`UI-010B` — Status: `Complete`

## Title

Add Backup and Snapshot Administration

## Related Specification(s)

- [Snapshot Specification](../../Backend/Specifications/Snapshot-Specification.md).
- [Operation Logging](../../Backend/Specifications/Operation-Logging.md).

## Goal

Allow an Admin to inspect, create, and clean up Backend-controlled Backup and
Snapshot resources with truthful verification and retention evidence.

## Scope

- List safe metadata, type/reason/tag/time/retention/verification state.
- Manual creation where specified and retention cleanup with impact preview.
- Operation results and links; safe handling of missing/corrupt entries.

## Out of Scope

- Database Restore, handled by UI-010C.
- Browser-selected backup paths or deletion outside retention policy.

## Dependencies

- UI-010 and authenticated Admin Snapshot/Backup APIs.
- Resolved terminology and lifecycle distinction between Backup and Snapshot.

## Implementation Steps

1. Define redacted list/action read models and retention semantics.
2. Build list, create, verify, and cleanup interactions.
3. Add success, partial cleanup, corruption, retry, cancellation, and unauthorized tests.

## Acceptance Criteria

- Only Backend-discovered resources under configured roots are presented or acted upon.
- Cleanup preview identifies count/retention effect and cannot accept arbitrary paths.
- Failed verification or cleanup never displays success; partial outcomes enumerate durable results.
- UI does not expose unnecessary absolute paths or internal exception detail.

## Verification

- Run focused Snapshot/Backup API tests with disposable roots.
- UI-010D verifies integrated browser behavior.

## Risks or Notes

- If current endpoints predate `/api/v1` role enforcement, API hardening is a prerequisite rather than UI work.

## Result

- Added the Admin-only recovery-point catalog, manual creation, integrity
  verification, and reviewed retention-cleanup interactions.
- The UI accepts no filesystem paths and displays no Backend absolute path.
- Reader denial, disposable creation/verification, zero-impact cleanup
  cancellation, and API redaction are covered by browser acceptance.
