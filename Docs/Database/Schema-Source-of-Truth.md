# Curator Database Schema Source of Truth

> Documentation status: Current  
> Owner: Database  
> Last verified: 2026-08-11

## Purpose

This document identifies where Curator's physical SQLite schema is actually
defined today. It is the routing authority for schema documentation; it does
not replace SQL migrations or authorize schema changes.

## Current conclusion

Curator has one Backend-owned ordered migration path. `0000_base_catalog.sql`
creates the canonical base catalog from an empty SQLite file; `0001` through
`0014` upgrade it through historical metadata, AI Workspace/Dispatch, and
Authentication/operational workflow persistence. The runner records every
step, verifies integrity/FKs, and is safe to replay.

Repository `CREATE TABLE IF NOT EXISTS` calls remain defensive compatibility
guards. They are not independent design authority and must remain structurally
compatible with the migrations. Test fixtures are acceptance inputs only.

## Authority rules

| Schema category | Current authority | Supporting evidence | Not authoritative |
| --- | --- | --- | --- |
| Base asset catalog (`status`, `model`, `studio`, `album`, relationship tables, `photo`) | `0000_base_catalog.sql`, evolved by later migrations | Repository/service/API tests and disposable introspection | Test fixtures or a deployed DB copy |
| Historical `workspace_album` | Existing deployed schema plus MT-008 archival migration | `archive_workspace_album.py`, MT-008 tests and historical docs | Active client/API models |
| Versioned AI Workspace/Dispatch additions | `apps/backend/migrations/0003`–`0013` SQL | Migration tests and matching Repository contracts | Mermaid diagrams or runtime-created test copies |
| Authentication | `0014_authentication_and_operations.sql` | Defensive AuthRepository DDL and auth tests | Repository access order |
| Import/Repair/Issue/Operation/Recovery persistence | `0014_authentication_and_operations.sql` | Defensive Repository DDL and workflow tests | Repository access order |
| Migration bookkeeping | `migrations/runner.py` definition of `schema_migration` | Migration tests | Migration README prose alone |

For actual behavior, SQLite introspection of a reviewed disposable copy is the
final verification evidence. It does not turn an unmanaged runtime database
into versioned schema source.

## Table-to-source inventory

### Base asset catalog and historical workspace

| Tables | Declared source today | Status |
| --- | --- | --- |
| `status`, `model`, `studio`, `album`, `album_model`, `album_relation`, `photo` | `0000_base_catalog.sql`, then ordered migrations | Active canonical schema |
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
| `0017` | `ai_instruction_profile`, `ai_instruction_profile_version`; Profile binding on `ai_model_configuration` |
| `0018` | Normalize the default AI Instruction Profile Dataset identity to `album_analysis` |
| `0025` | `ai_review_translation_cache` derived Review-assistance cache |

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

These are defined by ordered migration `0014`; matching Repository DDL is a
defensive compatibility layer.

## Construction and upgrade behavior today

1. `python3 -m apps.backend.migrations` creates a missing SQLite file or opens
   an existing one and determines unrecorded migrations.
2. Before its first write it creates and verifies a SQLite backup.
3. It applies unrecorded `0000`–`0014` sources in order in one transaction,
   checking integrity and foreign keys after each step.
4. Existing matching `album.remark` is adopted safely. Active historical
   Workspace rows cause a refusal until the guarded MT-008 command validates
   and archives them; the generic runner never guesses that business decision.
5. A current replay performs verification and creates no second backup.

## Test fixture role

`workflow_support.py`, `test_repositories.py`, `test_services.py`, and
`test_api_contract.py` create disposable base schemas. They are acceptance
fixtures: they make assumptions explicit and isolate tests from live data.
They do not define production installation or migration order. A fixture/schema
disagreement is a test or implementation gap, not permission to pick whichever
shape is convenient.

## Rule for future schema changes

- add an approved Backend task and controlling Specification change when behavior changes;
- add a numbered, rerunnable migration for persistent schema changes;
- keep any Repository compatibility DDL structurally identical and tested;
- update `Schema-Catalog.md`, affected diagrams, and persistence workflow docs;
- test against a disposable database and run migration plus full Backend regression;
- never use a live Curator database to generate or validate documentation.

The machine-readable inventory and drift gate introduced by DBDOC-006 verify
that this ordered result remains aligned with documentation.

The committed `schema-inventory.json` records tables, columns, FKs, unique and
explicit indexes, and ordered migrations. SQLite CHECK expression text is an
explicitly documented exclusion because no stable PRAGMA exposes it separately.

Historical field and relationship semantics are preserved in
[Historical Workspace Album](Historical/Historical-Workspace-Album.md), not in
the active diagram set.
