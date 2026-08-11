# Curator Conceptual Data Model

> Documentation status: Current
> Owner: Project documentation
> Last verified: 2026-08-11

## Purpose and lifecycle labels

This document describes domain meaning independently of SQL. Concepts are
labeled `Current`, `Approved`, or `Future` so an idea cannot be mistaken for an
implemented table, API, or UI.

## Current core concepts

### Album

Album is the current digital-asset management unit in apps.web. It represents a
durable collection with identity, canonical filesystem path, Studio, business
Status, title, dates, description, rating, remarks, Models, Photos, and related Albums.

Deleting or purging an Album is not ordinary CRUD: its future Trash lifecycle
must account for contained Photos/files and requires the blocked BT-033–035 and UI-010E work.

### Photo

Photo is a durable file-level asset record belonging to an Album. It supports
metadata and AI evidence identity, but apps.web intentionally does not provide a
general “browse Album Photos” management entry point. The Backend can discover
and transfer selected image evidence without requiring every file interaction
to become a Photo-management UI.

The future native curator may make Photo a direct curation unit; that is not a
current apps.web contract.

### Studio, Model, Status, and Album Relation

- Studio identifies the publisher/source responsible for Albums.
- Model identifies a person associated with one or more Albums.
- Album–Model is explicit many-to-many context with role/remarks.
- Album Relation represents durable Album-to-Album meaning such as `BELONGS_TO`.
- Status is Album business classification. It does not represent Dispatch,
  Worker execution, review, Repair, or Trash state.

### Operation, Issue, Repair, and recovery evidence

Operation is durable cross-workflow audit/recovery history. Issue and Repair
represent reviewable inconsistency and resolution state. Quarantine isolates
operational filesystem items safely; it is not Digital Asset Trash. Snapshots
are Backend-controlled recovery artifacts selected by risk.

## Current work and AI concepts

### Work Dispatch

A Dispatch Batch is one Admin-confirmed Album selection for a Worker kind. Each
Album gets a Group and one active Reservation. Album is exclusive across all
Worker kinds while that Reservation exists. A Group may contain several
adapter-owned Work Items—for example, different model configurations used to
compare Album-name analysis quality.

Release removes active ownership but retains Batch, Group, Items, results,
review, closure, and Operation history. Redispatch creates new identities.

### AI Workspace and Dataset Schema

AI Workspace is a versioned dataset container, not the historical
`workspace_album` table. Dataset Schema defines the type/version of items and
results the Workspace accepts. Workspace closes and archives with indefinite
audit evidence.

### AI Model Configuration

A managed llama.cpp configuration records model identity, prompt versions,
sampling count, runtime parameters, enabled state, and version. Each Work Item
stores a configuration snapshot so later configuration edits cannot rewrite
the meaning of an existing result.

### Work Item, attempt, evidence, and result

Work Item is one adapter-specific unit of execution against one Album and model
configuration. Claims create leased Attempts. Backend-selected Photo evidence
is frozen in a Manifest with ordered file identity, size, modification time,
hash, and MIME metadata.

AI result submission has two immutable stages:

1. Vision analyzes selected images and produces structured Album understanding.
2. Writer uses that analysis to produce several recommended Album names.

Current result state is a projection; immutable stage records preserve evidence.

### Review, Rework, and Promotion

Review state is separate from Worker run state. An Admin may approve, reject,
or request rework; evaluation/rating belongs to a Work Item result. Rework
creates a successor Work Item in the same Group, inherits configuration, and
retains predecessor lineage.

Approval does not itself mutate Album. Promotion is a separate reviewed action
that applies one selected name. Multiple configurations may analyze the same
Album, but only one successful Workspace+Album Promotion can win.

## Historical concept

The old `workspace_album` staging model normalized names/paths and materialized
permanent Albums. It is archived, unavailable to active clients, and not the
generic parent of current AI Workspace. Its semantics are preserved only in
[Historical Workspace Album](Database/Historical/Historical-Workspace-Album.md).

## Approved but not implemented

Digital Asset Trash is approved as the boundary for removing Albums or Photos
from the active library and eventually purging files. Detailed lifecycle,
retention, cascade, restore, and purge behavior remains blocked in BT-033–035
and UI-010E and must not be inferred from Repair Quarantine.

## Future concepts

The macOS native curator may provide Apple Photos-like browsing, self-organized
Albums, Photo-level Trash, and curation experiences over the same Backend-owned
asset library. Generic Assets beyond Photos, Annotations, embeddings, face
clusters, similarity, tags, and Rename Plans remain future concepts unless an
approved Architecture/Specification promotes them.

See [macOS Native Curator Memo](Project/macOS-Native-Curator-Memo.md). Memos do
not authorize implementation.

## Invariants

- Backend and database own durable identity and state; clients use APIs.
- Filesystem location and database metadata must remain explicitly reconcilable.
- Album business Status is independent of work/review/recovery state.
- AI evidence and model configuration are bound to the result they produced.
- Human approval controls permanent AI-recommended business changes.
- Current projections may change; audit, decisions, results, and released work history remain.
