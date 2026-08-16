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

Active and History views, stable Group routes, and Workspace summaries provide
resume points after navigation, browser refresh, delayed Worker activity, or a
Backend restart. Cancellation, abandonment, and release are explicit
Backend-controlled Group actions with visible blockers and Operation evidence.
Active and History render every Album/configuration run separately with a
human-readable stage, durable run/result states, attempt count, last activity,
active lease deadline, redacted failure, and a stable detail route. The stage is
a projection of authoritative Backend state, not a browser-owned progress bar.

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

Approval freezes one recommendation or a validated human revision. Rating is
optional from 1–5; Reject and Rework require a reason. Rework creates a linked
successor Work Item in the same Group and preserves prior results and decisions.

AI suggestions, human revisions, and the final accepted value are visibly
distinct. Versioned browser-local Review drafts survive navigation, refresh,
and browser restart, then reconcile with authoritative Backend versions. Stale
drafts offer rebase or discard behavior instead of silently overwriting newer
decisions.

## Promotion and completion

Approval and Promotion are separate. After approval, the Admin reviews the
exact selected name and Status change, explicitly acknowledges the displayed
change, and executes a Backend-bound Promotion without retyping the approved
name. A successful Promotion updates the existing permanent Album's
`album.title`, changes its Status according to the Backend contract (currently
`NAME_GENERATED`), records one Promotion winner and Operation evidence, and
prevents a duplicate winner. It does not create a new Album and AI output is
never promoted automatically.

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
