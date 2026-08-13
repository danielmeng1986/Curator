# UI-024 — Preserve Entity Editing Context

## Task ID

`UI-024` — Status: `Ready`

## Title

Preserve Unsaved Entity Drafts and List Navigation Context

## Related Specification(s)

- [UI Specification](../Specification.md), sections 4.1, 4.3, 4.5, and 5.
- [Entity Management](../03_Entity_Management.md).

## Goal

Prevent Writer input and list context from disappearing silently during normal
Album, Model, Studio, and Status management.

## Scope

- Dirty-state tracking for entity detail forms and Album relationship edits.
- Explicit Save, Discard, and Continue editing behavior on route/navigation attempts.
- Validated, version-tolerant browser drafts for appropriate new/edit forms.
- URL-backed list search, sorting, pagination, and return-to-list context.

## Workflow Contract

- Entry and preconditions: Writer opens an entity list or writable detail route.
- States and next actions: clean, editing/dirty, saving, saved, validation failed, conflict/failed, discarded.
- Persistence and recovery: navigation warns; refresh/browser restart restores a compatible draft or clearly offers discard; saved state clears the draft; Backend restart retains local input.
- Completion evidence: success identifies the saved entity and returning to the list restores prior filters/page.
- Failure safety: failed saves retain values and relationship edits; stale/incompatible drafts never overwrite Backend state automatically.

## Out of Scope

- Collaborative multi-user merge editing.
- Persisting plaintext authentication material inside entity drafts.

## Dependencies

- UI-002 shared feedback and UI-012 entity browser fixtures.

## Implementation Steps

1. Define shared draft keys, schema version, entity identity/version, expiry, and removal rules.
2. Add dirty navigation guard and restore/discard UI to entity forms.
3. Encode list state in route query parameters and restore it on Back/detail return.
4. Add browser interruption and stale-draft acceptance.

## Acceptance Criteria

- Accidental navigation cannot silently discard unsaved field or relationship changes.
- Refresh and browser restart restore a compatible draft in the same browser profile.
- Save or explicit Discard removes the draft; another entity cannot consume it.
- Search/filter/page state is shareable/restorable through the URL without including sensitive data.
- Reader routes never create writable drafts and direct writes remain denied.

## Verification

- Entity browser acceptance with navigation, refresh, context close/reopen, failed save, successful save, and discard scenarios.
- Backend entity regression for durable and zero-side-effect assertions.

## Risks or Notes

- Draft restoration must compare entity identity and Backend version to avoid
  silently applying old input over newer durable data.
