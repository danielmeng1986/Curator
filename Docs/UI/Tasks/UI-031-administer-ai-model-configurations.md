# UI-031 — Administer AI Model Configurations

## Task ID

`UI-031` — Status: `Complete`

## Title

Add Administrator Management for AI Model Configurations

## Related Specification(s)

- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- [AI Worker deployment manual](../../User-Manual/zh-CN/worker/ai-worker.md).
- `BT-045` managed llama.cpp model configuration contract.

## Goal

Let an Administrator create, inspect, edit, enable, and disable the portable
model configurations required by Album Work Dispatch, including a recoverable
empty state when no enabled configuration exists.

## Scope

- An Admin-only AI Model Configuration management route and an entry from the
  Administrator Center or AI Work Dispatch surface.
- List and detail projections for enabled and disabled configurations.
- Create and edit forms for the existing Backend fields, validation bounds,
  optimistic version checks, and structured conflict recovery.
- Enable and disable actions that preserve historical Work Item snapshots.
- A Work Dispatch empty state with a direct create-configuration action.
- Clear operator guidance that `model_file` is a portable path relative to the
  AI Worker's `--model-root`, not a Backend filesystem picker or absolute path.
- Focused UI contract tests, role-denial coverage, and real-browser acceptance.
- User-manual instructions for creating the configuration before the first
  dispatch.

## Out of Scope

- Uploading, downloading, discovering, or validating model files on a remote
  Worker host.
- Storing host paths, executables, Tokens, passwords, or other Worker-local
  secrets in a model configuration.
- Changing the `BT-045` configuration schema or Backend CRUD contract.
- Assigning configurations or Work Items to a particular Worker device.
- Editing immutable configuration snapshots already stored on Work Items.

## Dependencies

- `BT-045` — versioned model configuration validation and CRUD operations.
- `UI-002`, `UI-003`, and `UI-010` — shared feedback, disposable fixtures, and
  Administrator Center navigation.
- `UI-011E` and `UI-030` — Dispatch configuration selection and summary display.

## Product and Interaction Contract

1. Only an Administrator can open or mutate the management surface.
2. The list distinguishes enabled and disabled records and shows name, model
   identifier, portable model file, prompt versions, version, and updated time.
3. Create and edit expose all fields accepted by the current Backend contract:
   name, model identifier, optional repository, model file, Vision and Writer
   prompt versions, sample count, context size, threads, GPU layers, maximum
   tokens, temperature, image maximum tokens, and bounded additional parameters.
4. Numeric controls disclose the Backend bounds and preserve zero as a valid
   value where the contract permits it.
5. Invalid input and stale-version conflicts remain in the form with actionable
   feedback; they never appear as successful saves.
6. Disablement prevents new dispatch selection but does not alter existing Work
   Items or their immutable configuration snapshots.
7. When Work Dispatch has no enabled configuration, it explains why Preview is
   unavailable and links directly to creation. After a successful create, the
   operator can return to Dispatch and see the new enabled configuration without
   manually repairing database state.
8. The UI never presents a Backend file browser for `model_file` and never
   implies that Backend validation proves the file exists on every Worker.

## Implementation Steps

1. Add the Admin route, navigation entry, list/detail states, and permission
   disclosure.
2. Build reusable create/edit form normalization for all existing fields and
   Backend bounds, including bounded JSON additional parameters.
3. Add reviewed enable/disable actions and stale-version refresh behavior.
4. Connect the Work Dispatch empty state to the management route and preserve a
   safe return path to Dispatch.
5. Update the AI Worker manual with the first-configuration workflow and path
   boundary.
6. Add UI contract and Playwright scenarios for empty, create, edit, disable,
   re-enable, validation, stale conflict, and non-Admin denial states.

## Acceptance Criteria

- An Administrator starting with an empty `ai_model_configuration` table can
  create an enabled configuration entirely through the Web UI and then select
  it in Work Dispatch.
- All current Backend configuration fields and validation bounds are represented
  accurately; valid zero values are not rejected by browser-side validation.
- Editing uses the expected version and presents a recoverable stale conflict.
- Disabled configurations remain visible to Admins, disappear from new Dispatch
  selection, and do not change historical Work Item snapshots.
- Reader and Writer principals cannot discover or invoke configuration mutations,
  including through direct requests.
- Model paths and secrets are not uploaded, browsed, logged, or inferred by the
  UI.
- The Chinese AI Worker manual explains how an Admin prepares the required
  configuration before Preview dispatch.

## Verification

- Focused JavaScript UI contract tests.
- Disposable Backend API coverage for create, update, enable, disable, bounds,
  authorization, and optimistic conflicts.
- Playwright acceptance from an empty database through a configuration becoming
  selectable in Work Dispatch.
- Existing Work Dispatch and AI Workspace regression suites.

## Risks or Notes

- A configuration records portable runtime intent, not proof that a particular
  Worker has the referenced model. Worker capability and runtime compatibility
  routing are deliberately deferred to a separate contract.
- Disabling is the supported retirement action; destructive deletion would break
  historical traceability and is not part of this task.

## Completion Record

- Added the Admin-only AI Model Configurations route, Administrator Center entry,
  and create/edit/enable/disable workflow for every managed Backend field.
- Added a recoverable Work Dispatch empty state that takes an Administrator to
  configuration management and preserves the distinction between portable model
  intent and Worker-local files.
- Added contract and browser acceptance for authorization, empty-table creation,
  zero-valued parameters, optimistic conflicts, disable/re-enable, and Dispatch
  visibility.
- Updated the English and Chinese AI Worker manuals with the required first-run
  configuration step and model-root path semantics.
- Completed on 2026-08-15; the full 15-suite UI readiness gate passed.
