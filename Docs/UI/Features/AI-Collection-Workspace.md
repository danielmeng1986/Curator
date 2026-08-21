# AI Collection Workspace

> Documentation status: Current
> Owner: UI
> Last verified: 2026-08-13

Routes: `#/work-dispatch`, `#/ai-workspaces`, and `#/ai-reviews`. Primary role:
Admin. Worker boundary: authenticated Writer API.

## Purpose

The AI Collection Workspace coordinates permanent Albums, exclusive work
dispatch, dataset-versioned Worker results, human Review, and explicit
Promotion. It supports asynchronous work: the Admin, Worker, and reviewer do
not need to remain in one browser session or act immediately after one another.

## Historical boundary

The historical `workspace_album` collection is closed and archived by MT-008.
It has no active Web route, navigation item, edit action, batch action, or
Promotion journey. Retained compatibility or historical-verification handlers
do not make it a supported UI surface, and its records are never loaded as
active inputs for the current Workspace.

## Workspace and dataset model

The current Workspace keeps four concerns distinct:

- dataset identity, schema version, configuration, evidence provenance, and
  immutable Worker results;
- human Review fields, selected recommendation or revision, rating, and reason;
- system-managed run/review/lifecycle state, versions, Operations, Issues, and
  permanent-entity links; and
- dataset adapters for variable result fields without duplicating transition or
  Promotion policy in the client.

## Album work dispatch

An Admin starts from **AI Work Dispatch**, filters the permanent Album catalogue,
chooses eligible Albums and one or more configurations, reviews a zero-write
Preview, and explicitly dispatches.

Each configuration choice shows the model identity/file, evidence sample count,
context and output limits, image-token limit, temperature, CPU threads, GPU
layers, and prompt versions. This lets the Admin compare execution intent before
creating one immutable configuration snapshot per Work Item.

The Available view contains only Albums for which the Backend reports no active
Album Work Reservation. Successful dispatch creates one Group per Album and
one Work Item per chosen configuration. One Album may have only one active
Dispatch Group across Worker kinds, so comparison configurations share the same
Group and reservation. Dispatch does not change `album.status_id`; Album
business Status, Worker run state, and human Review state remain distinct.

Worker Queue, Review, Closure, and History views, stable Group routes, and Workspace summaries provide
resume points after navigation, browser refresh, delayed Worker activity, or a
Backend restart. Cancellation, abandonment, and release are explicit
Backend-controlled Group actions with visible blockers and Operation evidence.
Worker Queue contains unreleased Groups with Pending, Claimed, or Failed runs.
Review contains unreleased Groups with ReadyForReview, InReview, or
ReworkRequested work and no earlier Worker obligation. Closure contains
unreleased Groups whose Worker and review work is terminal, including Approved,
Rejected, and Cancelled outcomes that still need Promotion, release, or closure.
History contains Released Groups. These views render every Album/configuration run separately with a
human-readable stage, durable run/result states, attempt count, last activity,
active lease deadline, redacted failure, and a stable detail route. The stage is
a projection of authoritative Backend state, not a browser-owned progress bar.
Long Dispatch pages provide synchronized navigation above and below the content,
including First, Previous, direct page entry, Next, and Last.
Cancelling a Failed Work Item preserves its Dispatch Group and therefore does
not return the Album to Available. Group detail explains the remaining
reservation and the next step: complete or cancel the other runs, enter
Closure, and choose **Release Group**. **Abandon Group** remains the exceptional
whole-Group recovery action; it also frees the reservation but records the
Group as Abandoned.
While Worker Queue or an Active Group detail route is visible, bounded native-JavaScript
polling refreshes only the progress region every five seconds. It pauses in a
hidden tab, avoids overlapping requests, backs off after failure, preserves an
active control and scroll position, stops on route exit or terminal Group state,
and retains manual refresh as recovery.

## Worker boundary and evidence

An authenticated Writer Worker claims an eligible Work Item through the API,
uses the Backend-selected Photo Evidence Manifest, and submits the supported
Vision then Writer schemas. The browser does not run the model and never treats
a missing or invalid stage as review-ready. Deterministic simulated payloads may
exercise this orchestration in acceptance tests without invoking `llama.cpp`;
that proves workflow behavior, not model quality.

## Human Review

The stable Review state machine is:

`ReadyForReview → InReview → Approved | Rejected | ReworkRequested`

AI Recommendation titles may show Backend-cached Simplified-Chinese machine
translations as a second, visually subordinate line. The Admin explicitly
requests missing translations with **Show Chinese translations**; an ordinary
page load never invokes the external provider. Existing cached translations
appear on later visits even when the provider is unavailable. **Hide Chinese
translations** changes only presentation and never deletes cache data.

The English title remains the radio value, final Recommendation, and Promotion
authority. Translation loading or failure stays inside the Recommendation
panel and cannot disable, clear, or alter Review drafts, decisions, navigation,
or Promotion. The UI labels the Chinese text as machine-generated review
assistance and never contains provider credentials or calls DeepL directly.

Approval freezes one recommendation or a validated human revision. Rating is
optional from 1–5; Reject and Rework require a reason. Rework creates a linked
successor Work Item in the same Group and preserves prior results and decisions.

AI suggestions, human revisions, and the final accepted value are visibly
distinct. Versioned browser-local Review drafts survive navigation, refresh,
and browser restart, then reconcile with authoritative Backend versions. Stale
drafts offer rebase or discard behavior instead of silently overwriting newer
decisions.

Queue and Review Detail refresh authoritative state while visible without
overwriting an active draft. Manifest images are fetched with Admin authorization
only as their gallery cards approach the viewport, converted to browser-memory
thumbnails, and released on route exit. Opening a thumbnail temporarily fetches
the original for inspection; no image is copied into the Web workspace or stored
as a database blob.

## Promotion and completion

Approval and Promotion are separate. After approval, the Admin reviews the
exact selected name and Status change, explicitly acknowledges the displayed
change, and executes a Backend-bound Promotion without retyping the approved
name. A successful Promotion updates the existing permanent Album's
`album.title`, changes its Status according to the Backend contract (currently
`NAME_GENERATED`), records one Promotion winner and Operation evidence, and
prevents a duplicate winner. It does not create a new Album and AI output is
never promoted automatically.

After Promotion, the completed detail remains visible with the durable resulting
name and linked evidence. A **Next review** action advances to one eligible item
from the same remembered Queue order; the Queue link retains its filters. Every
advance remains a separate human Review and Promotion rather than a batch action.
After successful Promotion, image content preview ends and only the immutable
Manifest metadata and its availability/audit lineage remain in the Review view.

The Album reservation remains active after Promotion until the Dispatch Group
is explicitly released. Workspace closure and archive require their own
Backend-reported preconditions; archived work stays readable and action-free.

## Verification ownership

- UI-011A–F cover Workspace, Review, Dispatch, and browser acceptance.
- UI-026–028 cover reviewed-action and interruption behavior.
- UI-029 proves one complete no-model Dispatch → Worker result → Review →
  Promotion journey and directly verifies the durable `album.title` outcome.
- The living status is recorded in the
  [Workflow Readiness Matrix](../Workflow-Readiness-Matrix.md).
