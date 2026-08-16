# UI-033 — Streamline AI Review and Live Dispatch Progress

## Task ID

`UI-033` — Status: `Complete`

## Title

Enable Fast Sequential Album Review and Automatically Refreshed Work Progress

## Related Specification(s)

- [UI Specification](../Specification.md), section 4.6 safe confirmation.
- [AI Collection Workspace](../Features/AI-Collection-Workspace.md), review,
  Promotion, and completion workflow.
- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md),
  Album-name Promotion policy.
- [API Specification](../../Backend/Specifications/API-Specification.md), AI
  Review and Promotion endpoints.
- `UI-026`, `UI-027`, `UI-029`, and `UI-030`.

## Goal

Let an Administrator process a large queue as a sequence of deliberate
single-Album reviews without retyping an already approved Album name, while
Work Dispatch progress updates automatically in the existing framework-free
Web client.

## Scope

- Replace exact selected-name re-entry in the Promotion confirmation with an
  explicit acknowledgement of the displayed current name, resulting name, and
  Status change.
- Preserve separate Review approval and Promotion persistence boundaries while
  offering a short, clear single-Album path through them.
- After successful Promotion, offer or automatically navigate to the next
  eligible item in the current Review Queue order while preserving active
  filters.
- Automatically refresh Active Work Dispatch and Dispatch Group detail progress
  using bounded native-JavaScript polling.
- Retain manual refresh, durable Backend state, signed Promotion Preview tokens,
  stale/version conflict handling, Operation evidence, and accessibility.
- Update the controlling Backend/UI specifications and request/response contract
  before implementation removes exact-name confirmation.
- Add focused contract, Backend, and real-browser acceptance coverage for the
  complete dispatch-to-review-to-promotion-to-next-item journey.

## Workflow Contract

- Entry and preconditions: an Admin opens Active Work Dispatch or an eligible AI
  Review Queue item; the Work Item and Workspace satisfy existing Backend rules.
- States and next actions: waiting/running/failed/completed progress updates
  automatically; review remains start/edit/approve/reject/rework; an Approved
  item may be previewed, explicitly acknowledged, promoted, and followed by the
  next eligible review item.
- Persistence and recovery: review drafts retain the `UI-027` lifecycle;
  refresh/navigation/browser or Backend restart reloads authoritative state;
  polling is restarted only on eligible routes and never duplicates a material
  action.
- Completion evidence: Promotion displays the durable resulting Album name,
  Status, and Operation evidence before moving onward; the completed item no
  longer appears as eligible in the same queue projection.
- Failure safety: closing or declining confirmation performs no Promotion;
  expired/stale previews require a new preview; polling failures retain the last
  truthful display, disclose degraded refresh, back off, and allow manual retry.

## Product and Interaction Contract

1. Promotion Preview visibly presents the current Album name, approved resulting
   name, and calculated Status transition.
2. The Admin explicitly acknowledges that displayed change with a checkbox or
   equivalent accessible control before `Confirm & Rename` is enabled.
3. The execute request remains bound to the signed, expiring, Admin-owned Preview
   token. The Backend revalidates the Workspace, Album, Review, selected name,
   versions, uniqueness, Snapshot policy, and winner constraints at execution.
4. The approved selected name is never copied into a free-text confirmation
   field merely to prove attention. Removing this field requires an explicit
   amendment to the current Backend Promotion specification and API contract.
5. Successful Promotion presents a `Next review` action. Automatic navigation
   may be enabled only when the destination is deterministically derived from
   the current queue/filter order and the success evidence remains perceivable.
6. No more than one Album is promoted by any user action. Queue navigation is a
   convenience and never implies batch approval or batch Promotion.
7. Active and Group Detail routes poll their existing read endpoints every five
   seconds while visible and relevant. The interval may be tuned after measured
   load testing without changing the interaction contract.
8. Polling pauses when the document is hidden, stops on route exit, prevents
   overlapping requests, and uses bounded backoff after failures.
9. Polling updates progress without resetting filters, pagination, focus, scroll
   position, open reviewed actions, or manual selections.
10. Polling stops when the displayed work is terminal and resumes on an explicit
    refresh or when new active work is loaded. Manual refresh remains available.
11. The implementation uses the existing native HTML/CSS/JavaScript architecture;
    adopting a frontend framework is outside this task.

## Out of Scope

- Multi-Album approval or Promotion, unattended bulk renaming, and “approve all”.
- Changing AI recommendation, rating, rejection, or rework semantics.
- Cross-device draft synchronization.
- WebSocket or Server-Sent Events infrastructure.
- Invented percentage progress not supplied by authoritative Backend state.
- A frontend-framework migration or broad UI redesign.

## Dependencies

- `UI-026` — reviewed material actions retain explicit preview and confirmation.
- `UI-027` — drafts and stale reconciliation remain unchanged.
- `UI-030` — existing authoritative per-Work-Item progress projection and manual
  refresh provide the polling read model.
- `BT-064` — completed the acknowledgement-based Backend Promotion contract and
  removed the exact selected-name confirmation dependency.

## Implementation Steps

1. Amend the Work Dispatch Workflow, API Specification, AI Collection Workspace,
   and relevant tests to replace exact-name re-entry with explicit acknowledgement
   while retaining token, version, uniqueness, Snapshot, and winner safeguards.
2. Update Promotion Preview/execute UI and Backend request validation, including
   accessible acknowledgement, stale/expired preview recovery, and durable
   success evidence.
3. Define stable next-item resolution from the Review Queue projection and add a
   success-to-next-review transition that retains filters and never skips showing
   the completed result.
4. Add a route-scoped native-JavaScript polling lifecycle to Active Dispatch and
   Group Detail with visibility pause, overlap prevention, terminal stop, bounded
   error backoff, and manual refresh fallback.
5. Update only changed progress regions so polling preserves operator context.
6. Extend contract and Playwright coverage, then run the complete UI readiness
   and Backend AI Workspace workflow gates.

## Acceptance Criteria

- An Admin can approve and promote one Album without retyping its selected name,
  after explicitly acknowledging a clear current-to-result preview.
- A forged, expired, replayed, stale, cross-Admin, conflicting, duplicate-winner,
  or unacknowledged execute request produces no unintended Album mutation.
- Successful Promotion visibly proves the durable Album name, Status, and
  Operation, then provides the correct next eligible review without losing the
  queue's filters or order.
- Reject, rework, cancel, modal close, validation error, network interruption,
  refresh, and browser/Backend restart retain their established safe behavior.
- Active Dispatch and Group Detail reflect Worker progress without a full-page or
  manual browser refresh, while preserving focus, scroll, pagination, and filters.
- Hidden or unrelated pages generate no progress polling; requests never overlap;
  terminal work stops polling; transient failures back off and remain manually
  recoverable.
- Reader and Writer principals gain no new UI route, Promotion, or progress API
  authority.
- The complete one-Album dispatch, Worker result, Review, Promotion, durable
  verification, and next-item journey passes in a real browser using native JS.

## Verification

- Backend Promotion service/API tests for acknowledgement, token binding,
  expected versions, replay, expiry, uniqueness, Snapshot, and winner safety.
- UI contract tests for confirmation markup, next-item resolution, polling
  lifecycle, backoff, terminal stop, and partial DOM refresh.
- Playwright coverage for sequential reviews, preserved filters, keyboard and
  focus behavior, delayed Worker progress, hidden-tab pause, network failure,
  route exit, and manual fallback.
- Existing AI Workspace, Work Dispatch, Review draft, interruption, simulated
  Promotion, permission, and full UI readiness suites.

## Risks or Notes

- `BT-064` made acknowledgement and the existing server-side state binding the
  controlling, tested Backend safety contract. UI-033 may build the remaining
  next-review navigation and live Dispatch progress on that completed boundary.
- At a queue size above 2,000 Albums, throughput must come from reduced repeated
  interaction and stable next-item navigation, not from weakening one-Album
  auditability or silently introducing bulk mutation.
- Five-second polling is the initial operational default. Backend traffic and
  worker duration should be measured before shortening it or adopting push
  infrastructure.

## Completion Record

- Retained the completed BT-064 acknowledgement boundary and added a durable
  Promotion success panel with the resulting Album, Promotion/Operation evidence,
  preserved Queue return filters, and a deterministic **Next review** action.
- Added route-scoped five-second native-JavaScript polling to Active Dispatch and
  Active Group detail with hidden-tab pause, overlap prevention, 10–30 second
  failure backoff, route/terminal stop, manual fallback, scroll retention, and
  focus-safe deferred region replacement.
- Added focused UI contract coverage, a real-browser automatic Pending-to-
  Cancelled progress transition without manual refresh, and a real-browser
  Promotion-to-next-review transition.
- Completed on 2026-08-16; AI Review, Work Dispatch, and deterministic simulated
  Promotion browser journeys plus both focused UI contract suites passed.
