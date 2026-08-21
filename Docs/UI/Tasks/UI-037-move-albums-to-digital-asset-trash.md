# UI-037 — Move Albums to Digital Asset Trash

## Task ID

`UI-037` — Status: `Complete`

## Title

Add the Reviewed “Move Album to Trash” Workflow

## Related Specification(s)

- Digital Asset Trash specification produced by `BT-033`.
- `BT-034` recoverable Album Trash Backend workflow.
- [UI Specification](../Specification.md).
- [UI Data Interaction Rules](../Data-Interaction-Rules.md).

## Goal

Let an authorized user safely remove an eligible Album from the normal Albums
catalog by moving its complete digital-asset directory to Digital Asset Trash.
The workflow must make clear that Album and Photo database evidence is retained,
Album business `status_id` is unchanged, and permanent asset deletion is not
part of this action.

## User Workflow Contract

1. A Writer or Administrator opens an existing Album at `#/albums/:id`.
2. The page requests `GET /api/v1/albums/:id/trash-readiness` and presents
   either **Move to Trash** or the Backend-provided reasons why it is currently
   unavailable.
3. Selecting the action requests
   `POST /api/v1/albums/:id/trash/preview`. No filesystem or database lifecycle
   change may occur during this step.
4. The reviewed-action surface identifies the Album, its path, contained Photo
   count, affected byte count, retention date, and the distinction among Album
   Status, catalog visibility, and asset availability.
5. The execute control remains disabled until the user explicitly acknowledges
   that the Album will disappear from normal Albums and its complete asset
   directory will move to Trash. Execution sends only the returned Preview Token
   to `POST /api/v1/albums/trash/execute`.
6. On success, the UI closes the Album detail, removes it from the normal list,
   clears any Album draft/selection state, and shows the durable Operation or
   Trash reference returned by the Backend.

## Scope

- A role-aware action on existing Album detail; no action on unsaved Albums.
- Readiness loading, eligible, blocked, previewing, reviewing, executing,
  succeeded, stale/expired, failed, and `NeedsRepair` presentation.
- Human-readable mapping for every structured Backend blocker, including active
  Work Reservation, non-terminal Group/Work Item, unfinished Review or
  Workspace, active Operation, non-active catalog state, and unavailable assets.
- Zero-write preview, explicit acknowledgement, single-submit execution, and
  safe re-preview after stale or expired state.
- Album-list and detail navigation behavior after success.
- Writer, Administrator, Reader, disconnected, and insufficient-scope behavior.
- Focused client-contract and disposable real-browser acceptance coverage.

## Out of Scope

- Database hard deletion of Album or Photo records.
- Permanent asset purge or empty-Trash behavior, owned by `BT-035` and
  `UI-010E`.
- Restore, retention Hold, release Hold, or Trash administration, owned by
  `UI-010E`.
- Batch Album Trash, independent Photo Trash, or routine Photo browsing/CRUD.
- Changing Album `status_id` as part of the Trash action.
- Automatically closing or releasing AI Work merely to make an Album eligible.

## Dependencies

- `UI-002` — shared permission, structured error, and feedback behavior.
- `UI-005` — Album list/detail and preserved list context.
- `UI-026` — reviewed material-action lifecycle and guarded confirmation.
- `BT-033` — approved lifecycle and vocabulary.
- `BT-034` — implemented readiness, preview, execute, authorization, and
  ReadModel behavior. This dependency is complete.
- `UI-010E` is a downstream administrative companion and does not block this
  task.

## Implementation Steps

1. Add a Digital Asset lifecycle section to existing Album detail, visually
   separate from editable Album Status and metadata.
2. Load readiness after Album detail succeeds. Render a retryable loading/error
   state without treating transport failure as ineligibility.
3. Expose **Move to Trash** to Writer and Administrator. Readers receive a
   truthful read-only explanation; hiding the control must not replace Backend
   authorization.
4. Translate structured blockers into specific guidance and, when identifiers
   are supplied, links to the relevant Dispatch, Review, Workspace, Operation,
   Issue, or Repair record.
5. Implement the Preview Token confirmation through the shared reviewed-action
   component. Do not synthesize impact values from stale Album-page data.
6. Execute once, disable repeated input while pending, and use the Backend
   outcome as the only authority for navigation and feedback.
7. On stale/expired preview, keep the user on a stable Album context and offer a
   fresh readiness/preview cycle. On partial failure, do not claim the Album was
   removed; show `NeedsRepair` and link durable evidence.
8. Add API client-contract tests and a disposable browser/filesystem journey
   with eligible and blocked three-Photo Albums.

## Acceptance Criteria

- An eligible Album can be moved to Trash by Writer or Administrator from its
  detail page through exactly one reviewed Preview/execute cycle.
- The confirmation states the exact Album and Photo count and explicitly says
  the database records and Album business Status are retained.
- Successful execution makes the Album absent from `#/albums`, preserves the
  current list filters/page context, and does not render a false not-found error
  from an obsolete detail refresh.
- A blocked Album cannot be previewed or executed. The UI names each Backend
  blocker and never offers a local override or automatic Work closure.
- Reader, disconnected, and insufficient-scope users cannot mutate the Album;
  a direct unauthorized request remains rejected with zero change.
- Cancelling the review, closing through the supported explicit action,
  navigating away, refreshing, preview expiry, and stale lifecycle version
  produce no unintended filesystem or lifecycle mutation.
- Double-click, repeated execute, and delayed responses cannot produce a second
  move or contradictory success feedback.
- A failed or partial outcome is not reported as success. `NeedsRepair`, Issue,
  Repair, Operation, and Trash references are presented when returned.
- No Album hard-delete request is sent, and no independent Photo-delete action
  is introduced.

## Verification

- Client contract tests assert the exact readiness, preview, and execute paths,
  Preview Token handling, role gates, and structured-error mapping.
- Browser acceptance uses disposable archive and Trash roots and proves:
  eligible three-Photo success; active AI Work blocking with zero filesystem
  change; cancellation; stale preview; Reader denial; repeat submission; and
  normal Album list exclusion after success.
- Run existing entity-management, permission/disclosure, AI Work Dispatch, and
  reviewed-action regressions to ensure the new lifecycle action does not alter
  Album editing or Work ownership.

## Risks or Notes

- “Delete Album” is intentionally avoided as the primary label because the
  durable Album/Photo evidence remains. Destructive styling is still warranted
  because assets leave their normal location.
- Readiness is time-sensitive. The execute response, not the initially rendered
  button state, is authoritative.
- This task should be completed before adding Admin Trash restore controls so
  there is a browser-created recoverable item for the `UI-010E` journey.

## Completion Record

- Added a role-aware Digital Asset Lifecycle section to Album detail with
  Backend-owned readiness, specific AI Work/Review/Workspace/Operation
  blockers, and retryable readiness failure presentation.
- Added the guarded zero-write Preview and acknowledged execute flow, including
  exact Album path, Photo/file counts, byte size, retention date, retained
  database/Status disclosure, stale re-preview guidance, single-submit
  protection, durable Operation feedback, draft cleanup, and preserved list
  context after success.
- Extended the BT-034 preview read model with authoritative Album path and
  retention deadline; no lifecycle or authorization rule moved into the UI.
- Added a disposable two-Album browser scenario with isolated Archive and Trash
  roots. Acceptance proves Reader denial, active AI Work blocking, cancellation
  with zero mutation, changed-scope rejection, three-Photo success, normal
  ReadModel exclusion, database evidence retention, and physical movement of
  all files into Trash.
- Verification completed 2026-08-21: seven Web contract suites, focused Album
  management and feedback browser regressions, dedicated UI-037 browser and
  filesystem acceptance, and all 783 Backend tests pass.
