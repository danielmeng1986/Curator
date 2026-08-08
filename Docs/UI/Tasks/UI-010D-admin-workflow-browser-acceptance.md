# UI-010D — Add Administrator Workflow Browser Acceptance

## Task ID

`UI-010D` — Status: `Proposed`

## Title

Add Administrator Workflow Browser Acceptance

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md).
- [Snapshot Specification](../../Backend/Specifications/Snapshot-Specification.md).
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md).

## Goal

Prove the Administrator Center's bootstrap, access control, token management,
Backup/Snapshot, and Restore workflows through isolated browser scenarios.

## Scope

- First Admin success; wrong, expired, replayed, non-loopback, and second-bootstrap rejection.
- Registration approval/rejection, renewal, revocation, role/scope rules, and last-Admin protection.
- Backup/Snapshot creation/cleanup and database Restore success/failure.
- Durable Operation evidence, secret redaction, and zero-side-effect assertions.

## Out of Scope

- Re-testing every Authentication or Snapshot Service branch.
- Any test against the live Curator database or backup directory.

## Dependencies

- UI-003, UI-004A/B/C, UI-010, UI-010A/B/C, and their Backend API evidence.

## Implementation Steps

1. Define scenario-to-Backend-evidence mappings and exact durable assertions.
2. Implement Playwright workflows with disposable processes, stores, and roots.
3. Run twice from clean fixtures and retain sanitized artifacts on failure.

## Acceptance Criteria

- Reader/Writer cannot load or invoke Admin capabilities, including by direct requests.
- Rejected actions preserve exact database/filesystem/token state.
- Bootstrap and Token plaintext never appear in logs, screenshots, traces, or retained fixtures.
- Restore success/failure assertions inspect durable database and protective Snapshot state, not only page text.

## Verification

- Run the administrator browser suite twice, then Backend workflow-readiness and full regression.

## Risks or Notes

- Playwright tracing must be disabled or sanitized during secret-entry and one-time Token display steps.

