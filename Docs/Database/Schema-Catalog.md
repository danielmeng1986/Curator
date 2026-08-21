# Curator Database Schema Catalog

> Documentation status: Current  
> Owner: Database  
> Last verified: 2026-08-11

## How to use this catalog

This is the navigation catalog for Curator's persisted SQLite objects. It
summarizes purpose, identity, important relationships, constraints, lifecycle,
and source ownership. Exact SQL remains in the source named by
[Schema Source of Truth](Schema-Source-of-Truth.md).

Persistence roles used below:

| Role | Meaning |
| --- | --- |
| Current state | Mutable business state read by active workflows. |
| Configuration | Versioned or managed input to workflow execution. |
| Exclusive reservation | Short-lived ownership record preventing concurrent work. |
| Claim | Durable single-use binding between a reviewed preview and execution. |
| Immutable history | Append-only evidence or decision history. |
| Audit | Cross-workflow operational trace and recovery context. |
| Historical | Retained former model unavailable to active clients. |
| Bookkeeping | Internal migration/version tracking. |

`UUID` below means a stored text UUID. A reference stated as “logical” is
validated by Repository/Service code rather than a declared SQLite foreign key.

## Asset Catalog

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `status` | Current reference data | integer `id`; unique behavior enforced by service for `name` | Referenced by Album; referenced historically by Workspace Album | Base deployed schema; Repository/API contracts |
| `model` | Current business entity | integer `id`, business `uuid`; `display_name`, `primary_name` | Many-to-many Album relation through `album_model` | Base deployed schema; Model Repository |
| `studio` | Current business entity | integer `id`, business `uuid`; `name` | One Studio to many Albums | Base deployed schema; Studio Repository |
| `album` | Current or retained historical aggregate and apps.web management unit | integer `id`, business `uuid`; canonical `path`, title, dates, rating, `remark`; catalog/asset state and lifecycle version | FK intent to Studio/Status; Photos, Models, relations, Operations, Dispatch and AI work refer to Album | Base schema plus `0001`/`0023`; Album/Trash Specifications |
| `album_model` | Current relationship entity | integer `id`; Album/Model pair plus role, age, remarks | `album_id` → Album, `model_id` → Model; duplicate policy in Service | Base deployed schema; Repository Specification |
| `album_relation` | Current Album self-relationship | integer `id`; source/target/type tuple | source and related IDs → Album; no self relation; unique tuple required by current contract | Base deployed schema; Database model and Album API |
| `photo` | Current or retained historical asset/evidence metadata | integer `id`, business `uuid`; Album, filename/relative path, hash, dimensions, asset state | `album_id` → Album; apps.web does not expose general Photo browsing | Base schema plus `0023`; Photo/Trash and AI evidence contracts |

## Historical Workspace

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `workspace_album` | Historical, archived/retired; no active client access | integer `id`, optional `uuid`; former path/name/model inputs and archival evidence | former `album_id` → Album; `belongs_to_album_id` refers to another Workspace row, not Album | Base schema + MT-008/`0002`; BT-043 |

Do not confuse `workspace_album` with `workspace_album_ai_worker`. The former is
a retired import/review model; the latter is the active AI Work Item table.

## Authentication Administration

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `device_registration` | Current registration request/device identity and pending browser enrollment | UUID PK; device name/identity, requested/approved role/scopes, status, candidate Token hash, enrollment-proof hash/expiry | identity/role transition constraints and hash activation are Service-owned; never stores candidate Token plaintext | `AuthRepository`; Authentication Specification |
| `auth_token` | Current credential metadata; secret stored only as hash | UUID PK; registration UUID, token hash, scopes, expiry/revocation | FK → registration; active Admin safety is Service rule | `AuthRepository`; BT-040 |
| `token_renewal_request` | Current approval workflow/history | UUID PK; previous Token/registration, requested role/scopes, status and timestamps | FK → registration and previous Token; open-renewal behavior enforced by Service | `AuthRepository`; Authentication Specification |
| `admin_bootstrap_code` | One-time bootstrap credential state | UUID PK; code hash, expiry, use/lock state, failed attempts | only one current usable code by service policy; never stores plaintext | `AuthRepository`; UI-004A/B |
| `registration_proof_state` | Singleton managed Registration Proof state | fixed singleton PK; proof hash, create/rotate/disable/last-use timestamps | only hash is persisted; Admin generation/rotation reveals plaintext once | `AuthRepository`; Authentication Specification |

## Import, Operations, Repair, and Recovery

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `import_preview_claim` | Claim | preview UUID PK; claim time | one successful execution per reviewed preview | `ImportRepository`; BT-036 |
| `operation` | Audit | integer `id`, unique operation `uuid`; type, initiator, status, timestamps, entity/workflow links, error and recovery context | logical links across Imports, Repairs, Issues, Snapshots and AI workflows; role-sensitive disclosure | `OperationRepository`; Operation Logging Specification |
| `issue` | Current review state plus retained resolution | integer `id`, unique `uuid`; category, state, source workflow, priority/owner | affected Operation logical link; links via `issue_link` | `IssueRepository`; BT-038 |
| `issue_link` | Current/history relationship | Issue UUID, relationship, target UUID, created time | unique tuple; polymorphic target checked by workflow; logical Issue UUID link | `IssueRepository`; Issue Management Specification |
| `repair_case` | Current Repair state and durable outcome | integer `id`, unique `uuid`; Operation/Album UUID, expected path, state/category, verification | logical Operation and Album links; state machine in Service | `RepairRepository`; Repair Workflow |
| `repair_suppression` | Current bounded Admin policy | integer ID, unique UUID; fingerprint, scope path, expiry/revocation and reason | exact scope and authorization enforced by Service | `RepairSuppressionRepository`; BT-028 |
| `snapshot_cleanup_preview_claim` | Claim | preview UUID PK and claim time | single-use reviewed cleanup | `SnapshotCleanupRepository`; BT-041 |
| `restore_preview_claim` | Claim | preview UUID PK and claim time | single-use reviewed protected Restore | `RestorePreviewRepository`; BT-042 |
| `quarantine_item` | Current recoverable filesystem item plus retained outcome | integer ID, unique UUID; original/quarantine path, inventory, expiry/hold and restore fields | Repair/Operation UUID evidence; restore never overwrites | `QuarantineRepository`; BT-039 |
| `quarantine_preview_claim` | Claim | preview UUID PK and claim time | prevents replay of reviewed action | `QuarantineRepository`; BT-039 |
| `digital_asset_trash_item` | Recoverable Album asset Trash identity and retained restore/purge outcome | integer ID, unique UUID/Album; original/Trash relative paths, inventory digest/count/bytes, retention/hold, Trash/restore/purge Operations, purge actor/time and tombstone scope | FK → retained Album; one Trash identity per Album; path identity unique | migrations `0023`–`0024`; Digital Asset Trash Specification/BT-034/BT-035 |

Snapshot database files are filesystem recovery artifacts, not rows in a
Snapshot table. Their listing and validation are Backend-controlled.

## AI Dataset and Configuration

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `ai_dataset_schema` | Configuration/contract registry | composite PK `(dataset_type, schema_version)`; definition JSON; Active/Retired | referenced by AI Workspace | migration `0003`; BT-044 |
| `ai_workspace` | Current container, later retained history | integer `id`, unique UUID; dataset identity, title, Open/Closed/Archived state, version | composite FK → dataset schema; retention record extends closure/archive evidence | migration `0003`; UI-011A/B |
| `ai_workspace_retention` | Immutable lifecycle/audit evidence | Workspace UUID PK; outcome, reasons, actor/time/Operation fields | FK → AI Workspace; indefinite audit classification | migration `0013`; BT-052 |
| `ai_model_configuration` | Managed versioned execution configuration | integer `id`, unique UUID and name; model/prompt IDs, selected Instruction Profile version, sampling/runtime parameters, enabled/version | Work Items snapshot and reference configuration; provider currently `llama_cpp` | migrations `0004`, `0017`; BT-045/AIC-001 |
| `ai_instruction_profile` | Stable Administrator-managed AI instruction identity and lifecycle | integer `id`, unique UUID/name; Worker kind, Dataset type, Draft/Published/Disabled state, default/version | Owns immutable Profile versions; one published default per Worker kind/Dataset | migration `0017`; AIC-001 |
| `ai_instruction_profile_version` | Immutable executable AI instruction content | integer `id`, unique UUID; Profile/version, Global/Dataset/ Vision/Writer text, schemas, transport/composition and SHA-256 hash | FK → Instruction Profile; unique Profile/version | migration `0017`; AIC-001 |

## Work Dispatch

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `work_dispatch_batch` | Current then retained dispatch history | integer `id`, unique UUID; Worker kind, dataset/version, optional Workspace, state/version | Groups refer to Batch; created by Admin token | migration `0006`; BT-054/056 |
| `work_dispatch_group` | Current/released Album assignment history | integer `id`, unique UUID; Batch, Album, Worker/dataset identity, Active/Released state | FK → Batch and Album; history index by Album/time | migration `0006`; Work Dispatch Specification |
| `album_work_reservation` | Exclusive reservation; row deleted on release | Album ID PK; unique Group UUID, Batch UUID, Worker kind, reserved time | FK → Album/Group/Batch; one active reservation across all Worker kinds | migration `0006`; BT-054/057 |
| `work_dispatch_group_item` | Polymorphic Group-to-Worker-item relationship | integer `id`; Group, item kind/UUID, optional configuration UUID | unique item globally and within Group; only Group has physical FK | migration `0006`; BT-054/056 |
| `work_dispatch_preview_claim` | Claim | preview UUID PK; unique Batch UUID, claimant/time | one Batch execution per reviewed preview | migration `0007`; BT-056 |
| `work_dispatch_group_closure` | Immutable closure evidence | Group UUID PK; disposition, reason, actor, unique Operation, summary/time | FK → Group; Closed/Cancelled/Abandoned | migration `0012`; BT-057 |

## AI Work Execution and Evidence

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `workspace_album_ai_worker` | Current Work Item plus retained execution history | integer `id`, unique UUID; Workspace, Album, configuration UUID/snapshot, run state, lease/version | FK → Workspace, Album, configuration; adapter item linked from Dispatch Group | migration `0005`; BT-046 |
| `ai_work_item_attempt` | Immutable attempt history | integer `id`; Work Item UUID + attempt number unique; Worker token, lease, outcome/error | FK → Work Item | migration `0005`; BT-046 |
| `ai_work_item_regeneration` | Immutable failed-Work-Item regeneration lineage | predecessor/successor/root Work Item UUIDs, generation, actor/reason/time/Operation | FKs → Work Items; unique successor and bounded lineage enforced by Service | migration `0022`; UI-034 |
| `ai_photo_evidence_manifest` | Immutable evidence selection | integer `id`, unique UUID and Work Item; Album, sample/discovery summary, method/time | FK → Work Item and Album; one Manifest per item | migration `0008`; BT-047 |
| `workspace_album_ai_worker_photo` | Immutable selected Photo evidence | integer `id`, unique UUID; Manifest/Item/Album, ordinal, relative path, size/mtime/hash/MIME | FK → Manifest, Work Item, Album; unique ordinal and relative path within Manifest | migration `0008`; BT-047/048 |
| `ai_work_item_result_state` | Current result-stage projection | Work Item UUID PK; stage state, Vision/Writer result UUIDs, version/time | FK → Work Item; AwaitingVision → AwaitingWriter → ReadyForReview | migration `0009`; BT-049 |
| `ai_work_item_result_stage` | Immutable stage result | integer `id`, unique UUID; Work Item, Vision/Writer stage, schema and Manifest versions, payload/runtime hashes and JSON | unique `(work_item_uuid, stage)`; FK → Work Item/Manifest | migration `0009`; BT-049 |

## Human Review, Rework, and Promotion

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `ai_work_item_review` | Current review projection | Work Item UUID PK; state, rating/notes, selected name/source, reviewer/version | FK → Work Item; valid rating and selection-source checks | migration `0010`; BT-050 |
| `ai_work_item_review_decision` | Immutable decision history | integer `id`, unique UUID; Work Item, from/to state, evidence, actor/Operation/time | FK → Work Item | migration `0010`; BT-050 |
| `ai_work_item_rework` | Immutable lineage | old Work Item UUID unique; successor UUID unique; reason/actor/time | both logical/FK references → Work Item; successor inherits configuration contract | migration `0010`; BT-050/057 |
| `workspace_album_name_promotion` | Immutable Promotion outcome | integer `id`, unique UUID and preview; Workspace/Item/Album, selected/prior/result fields, outcome, actor/Operation/Snapshot | FK → Workspace/Item/Album; partial unique indexes allow only one successful Workspace+Album and Item winner | migration `0011`; BT-051 |
| `ai_promotion_preview_claim` | Claim | preview UUID PK; unique Promotion UUID, claimant/time | binds one reviewed Promotion preview to its outcome | migration `0011`; BT-051 |

## Migration bookkeeping

| Table | Role and lifecycle | Identity / important fields | Relationships and constraints | Source / contract |
| --- | --- | --- | --- | --- |
| `schema_migration` | Bookkeeping | migration ID PK; applied timestamp | no business relationships | migration runner; BT-059 target |

## Service-enforced rules not representable as simple foreign keys

- At least one usable Admin Token must remain.
- Album work is exclusive across all Worker kinds while a reservation row exists.
- Historical Workspace rows cannot return to active client access.
- Reviewed previews are integrity-bound, expire, and are single-use.
- Work Item leases, stage ordering, review transitions, and rework creation obey
  their Specifications even where the database stores only current state.
- Exactly one successful Album-name Promotion may win per Workspace and Album;
  partial unique indexes provide the final race-safe constraint.
- Quarantine Restore and protected database Restore never overwrite an existing target.

## Maintenance rule

Any persistent schema change must update this catalog, its authoritative source,
the affected domain diagram and persistence workflow, and the schema drift
inventory introduced by DBDOC-006. A task may not declare completion merely
because Repository code can create a missing table lazily.

Run the deterministic documentation gate from the repository root:

```bash
python3 tools/check_schema_docs.py
```

After an approved schema and documentation change, review the reported diff and
regenerate the machine-readable inventory explicitly with `--write`. The gate
uses a disposable canonical database and never opens the configured runtime DB.
