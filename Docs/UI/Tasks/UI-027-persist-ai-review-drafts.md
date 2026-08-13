# UI-027 — Persist AI Review Drafts

## Task ID

`UI-027` — Status: `Ready`

## Title

Protect Human AI Review Drafts Across Browser Interruptions

## Related Specification(s)

- [UI Specification](../Specification.md), sections 4.3–4.5 and 5.
- UI-011A/B Workspace and review state contracts.

## Goal

Prevent an Administrator's selected name, rating, evaluation, notes, and
decision reason from disappearing on refresh or browser restart.

## Scope

- Per-Work-Item, browser-profile-local review drafts.
- Draft schema/version, work-item version binding, expiry, restore, discard,
  success cleanup, and stale-state reconciliation.
- Navigation/refresh/browser restart/Backend restart acceptance.

## Workflow Contract

- Entry and preconditions: Admin opens an eligible Work Item review route.
- States and next actions: no draft, editing, restored, stale, submitting, accepted/rejected/rework requested, discarded.
- Persistence and recovery: input is saved locally as it changes and restored only for the same Work Item and compatible durable version.
- Completion evidence: accepted decision refreshes authoritative review state and removes obsolete local draft.
- Failure safety: validation/network failures retain input; concurrent durable change marks the draft stale and requires explicit copy/reconcile/discard rather than automatic submission.

## Out of Scope

- Cross-device draft synchronization.
- Editing immutable AI evidence or provenance.

## Dependencies

- UI-011C/D and the Backend expected-version review contract.
- Shared draft conventions established by UI-024 where reusable.

## Implementation Steps

1. Define bounded per-item draft storage and disclosure rules.
2. Restore compatible drafts and present explicit stale-draft reconciliation.
3. Clear drafts on terminal decision or explicit discard.
4. Add interruption, validation, network, and concurrent-review browser evidence.

## Acceptance Criteria

- Refresh, navigation away/back, browser restart, and Backend restart retain a compatible human draft.
- Another Work Item or browser profile cannot consume the draft.
- A concurrent decision never causes silent overwrite or accidental submission.
- Terminal decision and explicit Discard remove the local draft.
- Draft content is excluded from URLs, logs, traces, and retained failure artifacts.

## Verification

- Extended UI-011D browser acceptance with context close/reopen and stale version scenarios.
- Backend AI Workspace workflow regression.

## Risks or Notes

- Human notes may be sensitive; storage must be local, bounded, and cleared by
  documented lifecycle rules.
