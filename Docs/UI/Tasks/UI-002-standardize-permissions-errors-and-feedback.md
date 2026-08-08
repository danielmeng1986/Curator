# UI-002 — Standardize Permissions, Errors, and Feedback

## Task ID

`UI-002` — Status: `Proposed`

## Title

Standardize Permissions, Errors, and Operation Feedback

## Related Specification(s)

- [UI Data Interaction Rules](../02_Data_Interaction_Rules.md).
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md).
- [API Contract](../../Backend/Specifications/API-Contract.md) and [Authentication](../../Backend/Specifications/Authentication.md).

## Goal

Provide one reusable UI contract for role-aware actions, validation, failures,
conflicts, progress, and traceable operation results.

## Scope

- Reader, Writer, and Admin action presentation.
- Shared handling for 401, 403, validation, conflict/`NeedsRepair`, unavailable Backend, and safe unexpected errors.
- Pending state, duplicate-submission prevention, retained form input, result summaries, and Operation links.
- Accessible dialog, toast, inline error, and page-level summary patterns.

## Out of Scope

- Workflow-specific business decisions or client-side reimplementation of Backend policy.
- Visual redesign unrelated to these shared states.

## Dependencies

- UI-001 — identifies required roles and error outcomes.
- Canonical `/api/v1` error envelope.

## Implementation Steps

1. Define shared UI state and error-to-presentation mappings.
2. Implement reusable action, confirmation, validation, and result components in the current static client architecture.
3. Migrate existing pages and add component/contract tests for all mapped states.

## Acceptance Criteria

- Authentication and authorization failures are distinct and actionable without leaking sensitive detail.
- A pending mutation cannot be submitted twice; failure retains user input.
- A rejected action never displays success and exposes no claimed side effect.
- Status and severity are understandable without color alone, and dialogs support keyboard operation and focus restoration.

## Verification

- Extend `apps/web/tests/api_contract_test.mjs` for response mapping.
- Add focused browser scenarios for 401, 403, validation, conflict, retry, and duplicate clicks.

## Risks or Notes

- UI permission hiding is convenience only; Backend authorization remains authoritative.

