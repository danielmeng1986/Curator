# Work Dispatch Workflow

## Purpose and scope

This Specification defines how an Administrator selects Albums and dispatches
them to Backend-managed Worker workflows. It governs candidate queries,
preview, exclusive Album reservations, Dispatch Batches and Groups, Work Item
creation, cancellation, release, redispatch, Operations, and conflict handling.

The first adapter is `album_name_analysis`, implemented with AI Workspace Work
Items. Future Worker kinds may reuse dispatch orchestration without sharing the
AI result schema or changing the Album table.

## Architectural decisions

- `album.status_id` describes the business state of a digital asset. Dispatch,
  execution, and review states describe work performed against it. Dispatch
  must not overwrite Album Status.
- An Album is the exclusive scheduling unit. At most one active Work Dispatch
  Group may reserve an Album at a time, across every Worker kind, Workspace,
  field set, and Administrator session.
- A Dispatch Group represents one work purpose for one Album. Multiple model
  configurations for the same AI comparison are Work Items inside that Group;
  they are not competing Album reservations.
- The Backend owns eligibility, reservation, idempotency, and release rules.
  Clients never infer availability from Album Status or create Work Items in a
  loop as a substitute for batch execution.
- A physical Worker device is not selected during ordinary dispatch. The
  Worker kind identifies the queue; a Writer Token identity is recorded only
  when a device claims a Work Item.

## Persistent concepts

### Dispatch Batch

One Administrator-confirmed execution across a reviewed Album selection. It
retains its UUID, initiator, Worker kind, Workspace, selection summary,
configuration identities, preview identity, Operation, timestamps, and outcome.

### Album Work Reservation

The durable active ownership record for one Album. Active reservations enforce
a database uniqueness constraint on `album_id`. History is retained through
the owning Group and Batch after release; release does not erase prior work.

### Dispatch Group

One reserved Album plus one Worker kind and one Dataset/work specification. For
`album_name_analysis`, the Group belongs to an Open AI Workspace and contains
one Work Item per selected model configuration.

### Work Item

A concrete executable unit owned by the Worker-specific adapter. AI Work Items
retain the configuration snapshot, attempts, claims, results, review, and
Promotion evidence defined by the AI Workspace contracts.

## Candidate and eligibility contract

An Admin candidate query starts from the normal Album collection and supports
its stable search, Status, Studio, Model, rating, capture-date, publish-date,
and sort filters. It additionally accepts a Worker kind and may filter by
reservation or related-work summary.

The default dispatch-candidate view returns only Albums without an active
reservation. An Admin may request ineligible rows for explanation, but this
does not permit dispatch. Every row includes:

- stable Album identity and display fields;
- `can_dispatch`;
- stable `eligibility` code and human-readable reason when false;
- active reservation/Group summary when disclosure is authorized;
- relevant prior-work summary and warnings; and
- the Album version or equivalent state fingerprint used by preview.

Worker-specific adapters may add eligibility requirements, such as an
accessible Album path or the ability to build a Photo Manifest. Those rules
must not redefine the Album-wide reservation invariant.

## Preview contract

An Admin may select explicit Album UUIDs, the current page, or the first
bounded `N` Albums from a normalized filter and sort. “All filtered” is still
subject to a documented server-side maximum. Preview binds:

- exact Album identities and state fingerprints;
- normalized candidate filters and selection mode;
- Worker kind and Dataset/work schema version;
- Workspace and model configuration identities where applicable;
- expected Group and Work Item counts;
- eligibility, warnings, and conflicts; and
- an expiry time and authenticated Admin principal.

Preview performs no reservation, Work Item creation, Album mutation, or
Operation creation. A successful preview issues a signed short-lived token.

## Atomic execution contract

Execution accepts only the preview token. In one Backend transaction it:

1. claims the single-use preview and revalidates all bound state;
2. creates the Dispatch Batch;
3. inserts one unique active Album reservation and Group per Album;
4. creates the Worker-specific Work Items, including all selected AI model
   configurations inside the same Album Group; and
5. records the durable batch Operation and commits the complete outcome.

The first implementation is all-or-nothing. A stale Album, changed Workspace
or configuration, new reservation, invalid eligibility, replay, or uniqueness
race creates no partial Batch, Group, reservation, Work Item, or Album change.
Reservation conflict returns `409 ALBUM_WORK_RESERVATION_CONFLICT` with bounded
conflict details. Album Status remains unchanged on success and failure.

## Active reservation and release rules

An active reservation remains held while any part of the Group is queued,
claimed, retryable, awaiting review, in review, approved but unpromoted, or in
rework. A claim lease expiry and an individual Work Item failure, rejection, or
cancellation do not implicitly release it.

Release is a protected Admin workflow and is allowed only when the Group has
reached a documented terminal outcome: successful Promotion/closure; confirmed
closure after rejection; cancellation before material execution; or explicit
abandonment after every Work Item is terminal. Release is rejected while
running, review, rework, or pending Promotion obligations remain.

Release records actor, reason, time, Group version, and Operation. Redispatch
creates new Batch/Group/Work Item identities and preserves all earlier evidence.

## Album-name Promotion policy

Dispatch, Worker completion, and review approval never change Album Status.
Successful name Promotion atomically updates the selected Album name. The
dataset-specific Promotion policy may additionally map `TEMPORARY` to
`NAME_GENERATED`; for any other source Status the first implementation retains
the existing Status. Preview must disclose both the name change and any
calculated Status transition. A client cannot nominate the target Status.

Promotion requires a signed, expiring Admin preview bound to the Approved Work
Item/review version, selected name, Album title/Status/version, Workspace state,
and calculated Status. Exact name confirmation is required. A partial unique
database constraint permits only one `Promoted` winner for an Album within one
Workspace, while retaining failed attempts for audit and later safe retry.

## Album-analysis Photo evidence policy

The AI model configuration supplies `sample_count` (default 8). The Backend
recursively discovers regular JPG/JPEG, PNG, and WebP files beneath the Album
root, validates file signatures, rejects symlinks, and excludes files larger
than 32 MiB. It does not require or populate the permanent `photo` table.

Selection is deterministic. The Backend computes the arithmetic mean size of
all eligible images and prioritizes images within ±30 percent of that mean.
That pool is ordered by normalized relative path and sampled evenly. If the
pool is too small but the Album has enough eligible images, the Backend fills
it with images nearest to the mean size, using relative path as the stable
tie-breaker. Every selected file retains size, nanosecond modification time,
SHA-256, MIME type, ordinal, and relative path in one immutable Manifest.

Zero eligible images returns `EVIDENCE_IMAGES_UNAVAILABLE`. Fewer eligible
images than the configured sample count returns `EVIDENCE_SAMPLE_INSUFFICIENT`.
Both create an Album evidence Issue and no Manifest. A missing, replaced,
changed, oversized, or containment-invalid selected image returns
`EVIDENCE_CONTENT_CHANGED` before transfer or result acceptance.

## Authorization, Operations, and Issues

- Candidate, preview, execute, Group cancellation, and release are Admin-only.
- A Writer may claim and mutate only Work Items allowed by its Worker contract;
  it cannot create or release Album reservations.
- Dispatch execution and release require Operations linked to Batch, Group, and
  affected Album identities. A failed execution never reports success.
- Persistent anomalies or recovery needs create or link Issues under the
  applicable workflow; an Issue does not replace reservation truth.

## Required error outcomes

- `400 REQUEST_INVALID`: malformed filters, selection, Worker kind, or bounds.
- `403 FORBIDDEN`: non-Admin dispatch or release attempt.
- `409 DISPATCH_PREVIEW_STALE`: bound Album/configuration/Workspace state changed.
- `409 ALBUM_WORK_RESERVATION_CONFLICT`: any selected Album is actively reserved.
- `409 DUPLICATE_ACTIVE_WORK`: equivalent Work Items already exist inside the Group.
- `409 WORK_GROUP_NOT_RELEASABLE`: active execution, review, rework, or Promotion remains.

All conflict outcomes are zero-write outcomes and use the shared API envelope.

## Verification requirements

- Repository race tests prove one active reservation per Album.
- Preview/replay/stale tests prove all-or-nothing execution.
- Multi-configuration tests prove one Group can contain comparable Work Items
  without allowing a second Album reservation.
- Cross-Worker tests prove a different Worker kind cannot reserve the Album.
- Release and redispatch tests preserve history and reject premature release.
- Browser acceptance proves dispatched Albums leave the default candidate list
  and remain discoverable in active/history views.
