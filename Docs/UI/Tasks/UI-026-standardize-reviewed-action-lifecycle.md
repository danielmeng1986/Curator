# UI-026 — Standardize Reviewed Action Lifecycle

## Task ID

`UI-026` — Status: `Ready`

## Title

Make Material Preview, Confirmation, Abandonment, and Recovery Consistent

## Related Specification(s)

- [UI Specification](../Specification.md), sections 4.3–4.6.
- [UI Safety and Acceptance](../06_Safety_and_Acceptance.md).

## Goal

Ensure every material Preview has an explicit and truthful lifecycle instead of
being silently discarded by Escape, overlay click, navigation, or refresh.

## Scope

- Album batch update, Repair decision confirmation, Quarantine/Restore,
  retention cleanup, database Restore, Work Dispatch, AI Promotion, Workspace
  release/close/archive, and equivalent reviewed material actions.
- Shared non-dismissible reviewed-action surface or guarded dismissal behavior.
- Explicit **Cancel/Abandon review**, expiry/stale guidance, re-preview, and safe completion feedback.

## Workflow Contract

- Entry and preconditions: authorized role requests a Backend zero-write Preview or material confirmation.
- States and next actions: preparing, reviewing, acknowledged, executing, succeeded/partial/failed, expired/stale, explicitly cancelled.
- Persistence and recovery: accidental modal dismissal is prevented; navigation/refresh either resumes safe reviewed context or returns to a stable source entry with explicit re-preview guidance.
- Completion evidence: affected scope and Operation/Snapshot/Group/Item reference where available.
- Failure safety: cancellation and dismissal never execute; retries use fresh or still-valid preview identity according to Backend rules.

## Out of Scope

- Persisting typed destructive confirmation phrases.
- Weakening one-time Preview, stale-state, or replay protections.

## Dependencies

- Backend Preview/execute contracts for each included workflow.
- UI-002 modal and feedback primitives.

## Implementation Steps

1. Inventory all material preview/confirmation callers and assign risk/recovery behavior.
2. Add a shared reviewed-action component with explicit dismissal semantics and state labels.
3. Adapt each workflow without combining or reusing Preview Tokens across actions.
4. Add modal-close, Escape, overlay, navigation, refresh, expiry, stale, cancel, and retry acceptance.

## Acceptance Criteria

- Escape or overlay click cannot silently abandon a material reviewed action.
- Explicit cancellation names what is being abandoned and has zero durable/filesystem side effects.
- After refresh/navigation, the user can find the source workflow and understands whether to resume or generate a new Preview.
- Typed confirmation values are not persisted and are cleared after every attempt.
- Success and partial failure link to authoritative evidence where available.

## Verification

- Shared modal contract tests plus Admin, Repair/Quarantine, Dispatch, and AI Review browser suites.
- Backend stale/replay/cancellation and zero-side-effect regression.

## Risks or Notes

- Not every zero-write Preview needs long-term persistence. The requirement is
  an explicit, safe, understandable lifecycle, not indefinite Token storage.
