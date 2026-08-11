# Curator Database Schema Source of Truth

> Documentation status: Current  
> Owner: Database  
> Last verified: 2026-08-11

## Purpose

This document identifies where Curator's physical SQLite schema is actually
defined today. It is the routing authority for schema documentation; it does
not replace SQL migrations or authorize schema changes.

## Current conclusion

Curator does **not yet have one self-contained source that can create the full
current database from an empty file**. The schema is presently split across:

1. a pre-existing/base catalog schema assumed by the migration runner;
2. explicit versioned SQL migrations, primarily for AI Workspace and Dispatch;
3. defensive `CREATE TABLE IF NOT EXISTS` statements owned by Repositories;
4. test-only base fixtures that approximate the required starting schema.

This is documented truth, not the desired end state. BT-059 owns consolidation
of a canonical bootstrap and ordered migration execution. Until BT-059 is
complete, the authority rules below prevent tests or diagrams from being
mistaken for deployable schema source.

## Authority rules

| Schema category | Current authority | Supporting evidence | Not authoritative |
| --- | --- | --- | --- |
| Base asset catalog (`status`, `model`, `studio`, `album`, relationship tables, `photo`) | Existing deployed SQLite schema plus Repository query contract | Repository/service/API disposable fixtures and Database v0.2 docs | Any single test fixture as production bootstrap |
| Historical `workspace_album` | Existing deployed schema plus MT-008 archival migration | `archive_workspace_album.py`, MT-008 tests and historical docs | Active client/API models |
| Versioned AI Workspace/Dispatch additions | `apps/backend/migrations/0003`–`0013` SQL | Migration tests and matching Repository contracts | Mermaid diagrams or runtime-created test copies |
| Authentication | `AuthRepository._ensure_schema` DDL | Authentication service/API tests | Migrations (none currently define these tables) |
| Import execution claim | `ImportRepository` DDL | Import API/workflow tests | In-memory fixture omissions |
| Repair, suppression, Issue, Operation | Owning Repository defensive DDL and required-column upgrades | Repository/service/workflow tests | The smaller shared fixture definition by itself |
| Snapshot/Restore/Quarantine claims and items | Owning Repository defensive DDL | Admin and recovery workflow tests | Snapshot files or operational logs |
| Migration bookkeeping | `migrations/runner.py` definition of `schema_migration` | Migration tests | Migration README prose alone |

For actual behavior, SQLite introspection of a reviewed disposable copy is the
final verification evidence. It does not turn an unmanaged runtime database
into versioned schema source.

## Table-to-source inventory

### Base asset catalog and historical workspace

| Tables | Declared source today | Status |
| --- | --- | --- |
| `status`, `model`, `studio`, `album`, `album_model`, `album_relation`, `photo` | Pre-existing base database; shapes repeated in Backend test fixtures and Repository queries | Active; canonical bootstrap missing |
| `workspace_album` | Pre-existing base database plus MT-008 archive migration | Historical/archived |
| `schema_migration` | `apps/backend/migrations/runner.py` | Active bookkeeping |

Migration `0001` adds `album.remark`. Migration `0002` is not executed by the
default migration module; its guarded implementation is
`archive_workspace_album.py`. The base tables are preconditions, not products,
of the default runner.

### Authentication

| Tables | Current source |
| --- | --- |
| `device_registration`, `auth_token`, `token_renewal_request`, `admin_bootstrap_code` | `AuthRepository._ensure_schema` |

### AI Workspace and Dispatch

| Migration | Tables/indexed structures introduced |
| --- | --- |
| `0003` | `ai_dataset_schema`, `ai_workspace` |
| `0004` | `ai_model_configuration` |
| `0005` | `workspace_album_ai_worker`, `ai_work_item_attempt` |
| `0006` | `work_dispatch_batch`, `work_dispatch_group`, `album_work_reservation`, `work_dispatch_group_item` |
| `0007` | `work_dispatch_preview_claim` |
| `0008` | `ai_photo_evidence_manifest`, `workspace_album_ai_worker_photo` |
| `0009` | `ai_work_item_result_state`, `ai_work_item_result_stage` |
| `0010` | `ai_work_item_review`, `ai_work_item_review_decision`, `ai_work_item_rework` |
| `0011` | `workspace_album_name_promotion`, `ai_promotion_preview_claim` |
| `0012` | `work_dispatch_group_closure` |
| `0013` | `ai_workspace_retention` |

Repositories contain matching defensive DDL for several of these tables. The
versioned SQL migration is the declared design authority where it exists; the
Repository copy is a compatibility guard and must remain structurally
compatible until BT-059 removes or narrows the duplication.

### Operational workflow persistence

| Tables | Current source |
| --- | --- |
| `import_preview_claim` | `ImportRepository` |
| `repair_case` | `RepairRepository` |
| `repair_suppression` | `RepairSuppressionRepository` |
| `snapshot_cleanup_preview_claim` | `SnapshotCleanupRepository` |
| `restore_preview_claim` | `RestorePreviewRepository` |
| `quarantine_item`, `quarantine_preview_claim` | `QuarantineRepository` |
| `issue`, `issue_link` | `IssueRepository` |
| `operation` | `OperationRepository` |

These are current runtime schema contracts but are not yet represented by
ordered migration files. BT-059 must preserve their data and compatibility
when establishing canonical migration ownership.

## Construction and upgrade behavior today

1. The default runtime expects a configured SQLite database with base catalog tables.
2. `python3 -m apps.backend.migrations` checks that `album` already exists,
   creates a verified backup, and applies/adopts only migration `0001`.
3. MT-008 archival uses its separate guarded command and records migration `0002`.
4. SQL files `0003`–`0013` are versioned design sources and are exercised by
   migration tests, but the default runner does not currently iterate them.
5. Repository initialization creates or upgrades workflow-owned tables as the
   corresponding repository is used.

Therefore the migrations README statement that ordered migrations are applied
by the module is broader than current implementation. It must be corrected by
BT-059, not hidden in documentation.

## Test fixture role

`workflow_support.py`, `test_repositories.py`, `test_services.py`, and
`test_api_contract.py` create disposable base schemas. They are acceptance
fixtures: they make assumptions explicit and isolate tests from live data.
They do not define production installation or migration order. A fixture/schema
disagreement is a test or implementation gap, not permission to pick whichever
shape is convenient.

## Rule for future schema changes

Until BT-059 is complete:

- add an approved Backend task and controlling Specification change when behavior changes;
- add a numbered, rerunnable migration for persistent schema changes;
- keep any Repository compatibility DDL structurally identical and tested;
- update `Schema-Catalog.md`, affected diagrams, and persistence workflow docs;
- test against a disposable database and run migration plus full Backend regression;
- never use a live Curator database to generate or validate documentation.

After BT-059, its canonical bootstrap/migration contract supersedes the
temporary split-authority rules in this document and this file must be reverified.

Historical field and relationship semantics are preserved in
[Historical Workspace Album](Historical/Historical-Workspace-Album.md), not in
the active diagram set.
