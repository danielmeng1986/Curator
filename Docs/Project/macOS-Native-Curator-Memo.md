# macOS Native Curator Application — Product Memo

## Status

`Deferred product concept` — recorded for discussion after `apps.backend` and `apps.web` are deployed. This memo is not an approved implementation specification and creates no current delivery dependency.

## Context

`apps.web` exists as an authenticated digital-asset administration tool. It replaces inconvenient direct database editing and treats the permanent Album as its normal management unit. It is not intended to become the primary Photo browsing or curation experience.

## Current Product Idea

A future native macOS Curator application may provide an Apple Photos-like experience over the Curator library:

- Browse Photos and other digital assets as the primary user experience.
- Treat current permanent Albums as source-library groupings rather than the only way a user can organize a collection.
- Let users create self-organized Albums that reference library assets without changing their permanent source Album membership.
- Present AI Worker analysis and recommendations with the specific Photo evidence used to reach a conclusion.
- Keep AI suggestions non-authoritative until the user accepts them.
- Allow a user to move an individual Photo into Digital Asset Trash, similar to an operating-system or photo-library Trash experience.

## Administrative Boundary

The proposed division of responsibility is:

- The native application provides browsing, curation, self-organized Albums, AI-assisted review, and recoverable Photo-level Trash actions.
- `apps.web` remains the administrative tool for Album-level asset management, Trash inspection and recovery, retention/hold decisions, and final permanent purge (“empty Trash”).
- `apps.backend` owns authorization, lifecycle policy, filesystem/database consistency, verification, and durable Operation/Issue/Repair evidence for both clients.

## Data-Model Questions for Later Design

- Whether self-organized Albums are ordered collections, smart collections, or both.
- Whether Photo identity remains stable across source-Album moves, Trash, restore, and filesystem reorganization.
- How thumbnails, previews, and AI evidence derivatives are generated, cached, authorized, and invalidated.
- How the native application works offline and reconciles concurrent edits.
- Whether a Photo can belong to multiple self-organized Albums without copying its underlying asset.
- Which metadata belongs to the source asset, a Photo observation, an AI proposal, or a user-curated collection membership.
- How video and future asset types fit the same native experience.

## Safety Principles to Preserve

- Album remains the default destructive-management unit in `apps.web`.
- Photo-level removal is recoverable first; permanent deletion is a separate Admin-reviewed action.
- Digital Asset Trash is not Repair Quarantine and is not database Snapshot Restore.
- Destructive outcomes must reflect verified filesystem and database state.
- Partial failure must remain visible and recoverable rather than being called success or rollback.

## Revisit Point

Resume product and architecture design after `apps.backend` and `apps.web` reach their initial deployed state. At that time, promote accepted decisions from this memo into Architecture, data-model, API, native-client, and lifecycle Specifications before creating implementation tasks.
