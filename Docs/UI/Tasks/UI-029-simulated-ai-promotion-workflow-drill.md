# UI-029 — Simulated AI Promotion Workflow Drill

## Task ID

`UI-029` — Status: `Complete`

## Title

Verify Admin Dispatch, Simulated Worker Results, Review, and Album Promotion

## Related Specification(s)

- [UI Specification](../Specification.md), complete workflow acceptance.
- Backend [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- Backend [API Specification](../../Backend/Specifications/API-Specification.md), AI result and Promotion endpoints.

## Goal

Prove the complete Album naming workflow without starting `llama.cpp` or any AI
model: an Admin dispatches one Album, a deterministic simulated Writer submits
valid two-stage results, and an Admin selects and promotes one proposed name
into the permanent Album record.

## Scope

- Disposable database, archive, Admin browser, and Writer Token.
- One AI Workspace, configuration, Album, Dispatch Group, and Work Item.
- Admin UI dispatch and review/Promotion actions.
- Worker API evidence claim plus deterministic Vision and Writer payloads.
- Direct database verification of permanent Album, review, Promotion, result,
  reservation, and Operation state.

## Workflow Contract

- Entry and preconditions: Admin opens **AI Work Dispatch**; a Writer device can claim the configured Work Item.
- States and next actions: available → dispatched → claimed → Vision submitted → Writer submitted → ReadyForReview → InReview → Approved → Promoted.
- Persistence and recovery: authoritative state is durable; UI reloads Group/Review state from Backend. No model process state is required.
- Completion evidence: `album.title` equals the selected name, status is `NAME_GENERATED`, one Promotion winner and Operation exist, and the reservation remains until Group release.
- Failure safety: fixture resources are disposable; no live database, archive, model file, or network AI service is used.

## Out of Scope

- Assessing AI model quality, prompt quality, inference speed, or `llama.cpp` integration.
- Renaming a nonexistent `album.album_name` column. The permanent schema stores the Album name in `album.title`.
- Group release and Workspace closure, already covered by UI-011D/F and BT-053.

## Dependencies

- BT-043–058 and UI-011A–F.
- UI-017 disposable real-browser infrastructure.

## Implementation Steps

1. Create a dedicated one-Album browser fixture journey.
2. Dispatch through Admin UI and submit deterministic Worker API results.
3. Approve and Promotion through Admin UI.
4. Query the disposable SQLite database directly and assert the complete durable outcome.
5. Register the drill in UI readiness.

## Acceptance Criteria

- No `llama.cpp`, model binary, or external inference service is invoked.
- Admin UI creates exactly one Group and Work Item for the target Album.
- Simulated Worker submission uses the production schemas and authorization boundary.
- Admin selects one proposed name and completes Promotion through UI.
- Direct SQL proves `album.title` and status changed, exactly one successful Promotion/Operation exists, and two result stages plus one Approved review are durable.
- Fixture cleanup removes all temporary database and archive resources.

## Verification

- `apps/web/tests/simulated_ai_promotion_browser_acceptance.mjs`.
- Focused BT-053 service workflow acceptance.
- Complete UI readiness and Backend regression gates.

## Risks or Notes

- Deterministic fixture text proves orchestration and persistence only; it is not
  evidence that a real model produced a useful name.

## Completion Record

- The dedicated browser journey dispatches one Album through the Admin UI,
  submits production-schema Vision and Writer payloads with a Writer Token,
  and completes Review and Promotion through the Admin UI.
- Direct SQLite verification proves the selected value was stored in
  `album.title`, status became `NAME_GENERATED`, and the related result,
  Approved review, Promotion, Operation, and reservation records are durable.
- The focused browser drill and BT-053 service acceptance pass without starting
  `llama.cpp` or opening a model file. No product-contract gap was found.
