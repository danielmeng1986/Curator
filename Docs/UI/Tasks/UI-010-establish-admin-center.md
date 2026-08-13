# UI-010 — Establish Administrator Center

## Task ID

`UI-010` — Status: `Complete`

## Title

Establish Administrator Center Shell and Safety Policy

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md).
- [Snapshot Specification](../../Backend/Specifications/Snapshot-Specification.md).
- [UI Foundation](../Foundation-and-Navigation.md) and [UI Specification](../Specification.md).

## Goal

Create one Admin-only navigation and interaction boundary for authentication,
security, Backup, Snapshot, database Restore, Repair Quarantine, Digital Asset
Trash, and administrative history.

## Scope

- Admin route group, overview, capability navigation, authorization guard, and safe empty/loading/error states.
- Shared high-risk action pattern: impact preview, explicit confirmation, pending lock, result, and Operation link.
- Sections for UI-010A through UI-010C and links to UI-009/operation history.

## Out of Scope

- Implementing the section-specific workflows.
- Treating hidden navigation as an authorization control.

## Dependencies

- UI-001, UI-002, and UI-004C.
- UI specification amendment adding authentication, roles, and administration to scope.

## Implementation Steps

1. Specify routes, information architecture, role behavior, and high-risk interaction pattern.
2. Implement the shell and authenticated Admin guard.
3. Add navigation, direct-URL, role-change, and safe-error tests.

## Acceptance Criteria

- Only an authenticated Admin can load administrator data or invoke actions.
- Reader/Writer direct navigation is rejected safely and does not trigger protected fetches beyond the authorization check.
- High-risk sections use consistent confirmation and traceability patterns.
- Admin overview contains no plaintext credentials or unnecessary sensitive diagnostics.

## Verification

- Run client route/contract tests and focused browser access scenarios.
- UI-010D supplies integrated administrator acceptance.

## Risks or Notes

- An Admin Center raises the impact of browser credential compromise; its pages should avoid long-lived secret exposure and unsafe cached content.

## Completion Notes

- Added an Admin-only route and navigation entry with overview counts and
  capability readiness; unavailable sections remain disabled rather than
  linking to placeholder mutation pages.
- Reader/Writer route guards run before protected Admin fetches.
- Added one shared high-risk interaction pattern with impact copy, typed phrase,
  duplicate-action lock, safe cancellation, and structured result handling.
- Overview surfaces no Token plaintext/hash, registration proof, raw diagnostic,
  or arbitrary filesystem path.
