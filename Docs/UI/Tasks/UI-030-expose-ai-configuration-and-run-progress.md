# UI-030 — Expose AI Configuration and Run Progress

## Task ID

`UI-030` — Status: `Complete`

## Goal

Let an Admin understand which model settings will run before dispatch and then
follow every Album/configuration execution without interpreting Group counters.

## Scope

- Inspectable enabled-configuration summaries in the Available dispatch view.
- Per-Work-Item progress in Active, History, and stable Group detail routes.
- Authoritative run/result/review stage projection, attempts, last activity,
  lease deadline, failure summary, and detail navigation.
- Backend Group projection and browser acceptance coverage.

## Workflow Contract

- Entry: Admin opens **AI Work Dispatch** with at least one enabled configuration.
- Decision: every configuration card exposes the execution parameters relevant
  to model selection; selecting multiple cards creates comparable runs.
- Progress: the UI derives a readable stage from durable Backend run, result,
  and Review state and never invents a percentage.
- Recovery: Active, History, and Group detail reload the same authoritative
  progress after navigation, refresh, or Backend restart.
- Failure: failed runs retain attempt count, last activity, and an Admin-visible
  bounded failure summary without exposing a credential or Server path.

## Acceptance Criteria

- Configuration cards show model identity/file, sample count, context, output
  and image limits, temperature, threads, GPU layers, and prompt versions.
- Each Album/configuration pair has its own stage row and stable detail link.
- Active/History and Group detail provide an explicit progress refresh action.
- Pending, claimed/Vision, Writer, failed, completed, and Review states have
  truthful labels based solely on Backend fields.
- Contract and real-browser Work Dispatch acceptance tests pass.

## Completion Record

- Enriched Group projections with immutable configuration snapshots, result
  stage, timestamps, lease, attempts, and failure state.
- Replaced aggregate-only Active/History presentation with per-run progress
  tables, explicit refresh actions, and the same table in Group detail.
- Expanded configuration choices into readable parameter cards and documented
  the projection in the AI Collection Workspace feature description.
