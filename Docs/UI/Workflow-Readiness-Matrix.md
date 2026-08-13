# UI Workflow Readiness Matrix

## Gate contract

This matrix maps supported Backend workflow evidence to user-facing UI
outcomes. A Backend workflow can be Ready while its UI is Not Implemented; the
browser layer verifies client integration and does not repeat every Service
rule.

The [Curator Web UI Specification](Specification.md) controls readiness. Each
row must cover the applicable discoverability, state, modal-close, navigation,
refresh, browser-restart, Backend-restart, delayed-action, retry, cancellation,
and upgrade/cache boundaries—not only its uninterrupted happy path.

| Classification | Meaning |
| --- | --- |
| Ready | The named UI outcome exists and has isolated browser evidence. |
| Failing | The scenario runs and currently fails; it must not be skipped. |
| Not Implemented | Required page, API read model/action, or browser evidence does not exist. |
| Blocked by Specification | Product, security, dataset, confirmation, or recovery behavior must be decided first. |

All browser scenarios use disposable database, filesystem, archive, backup,
Token, Snapshot, log, and output resources. Rejected actions require a durable
zero-side-effect assertion. The final gate is owned by UI-016.

## Current workflow coverage

| Backend workflow evidence | Business/UI outcome | UI route and role | Happy-path browser owner | Required rejection/failure evidence | Classification / gap |
| --- | --- | --- | --- | --- | --- |
| BT-024 authenticated API workflow; `TestAuthenticatedApiWorkflow` | Connect an approved device and enter protected UI safely. | Connection dialog; Reader/Writer/Admin | UI-004C, UI-015 | Missing, invalid, expired, revoked, and insufficient-scope Token makes no business mutation. | Ready — role-isolated browser and direct-request evidence covers the complete credential-state matrix, reconnection, visibility, Backend enforcement, and zero business side effects. |
| Authentication registration/approval services and tests | Establish the first Admin; request Reader/Writer access; resume delayed approval; then review renewals, elevation, and revocation. | Persistent connection/status entry; first-run bootstrap; `/admin/devices`; requesting browser and Admin | UI-004A/B, UI-010A/D, UI-019–022 | Wrong/expired/replayed bootstrap, lost browser-local material, self-approval, last-Admin revocation, and unauthorized management preserve auth state. | Ready — multi-browser evidence covers UI-only request/approval, closed-dialog and refresh recovery, older saved-state compatibility, current-client cache delivery, automatic connection, role isolation, and credential redaction. |
| Entity repository/service/API regression | Manage permanent Albums, Models, Studios, Statuses, Photos, and relationships. | `/albums`, `/models`, `/studios`, `/statuses`; Reader/Writer | UI-005, UI-012, UI-024 | Validation, duplicate/self relation, reference-protected delete, Reader writes, interrupted drafts, and stale restore preserve prior state. | Ready — versioned drafts, guarded leave, stale-record protection, URL list context, durable verification, and browser-restart recovery pass. |
| BT-019 Import COPY, MOVE, database-only, preview; `test_import_workflow_acceptance` | Compose a resumable batch, review zero-write preview, and execute the selected filesystem/database mode with truthful results. | `/import/albums`; Writer | UI-006, UI-013, UI-025 | Invalid/collision/stale/cancelled/repeated/interrupted requests have no unintended mutation; partial failure matches durable/filesystem outcome. | Ready — compose, selection, Preview, result, Operation reference, explicit Abandon, refresh/restart recovery, and existing execution safety pass. |
| BT-020 failed Import to verified Repair; `test_import_workflow_acceptance` | See `NeedsRepair`, follow its Issue/Repair, make an allowed decision, and verify completion. | Import result → `/issues/:uuid`; Writer/Admin | UI-006–008, UI-014 | Client cannot force unsafe policy; invalid/stale/repeated decisions preserve state. | Ready — disposable browser evidence follows failed Import Operation links, exercises review decisions, and proves verified Repair state and history. |
| BT-022 Repair policy/suppression; `test_repair_policy_workflow_acceptance`, `test_repair_decision_workflow_acceptance` | Review automatic/assisted/manual classification; accept, reject, confirm, or suppress as authorized. | `/issues`, `/issues/:uuid`; Writer/Admin | UI-008, UI-014, UI-026 | Unsafe automatic rename, missing confirmation, implicit dismissal, unauthorized suppression, and invalid transition have zero unintended side effects. | Ready — durable decision safety plus non-dismissible reviewed actions, explicit cancellation, interruption guidance, and stale/retry evidence pass. |
| BT-022 Quarantine/Restore; `test_quarantine_workflow_acceptance` | Quarantine and restore individual filesystem items with verified traceability. | `/admin/quarantine`; Admin | UI-009, UI-014, UI-026 | Cancel, implicit dismissal, collision, missing item, replay, and non-Admin request preserve filesystem/durable state. | Ready — Preview execution safety, explicit cancellation, non-dismissible review, restart guidance, and linked durable evidence pass. |
| BT-023 cross-workflow trail; `test_traceability_workflow_acceptance` | Navigate Import → Issue → Repair → Snapshot/Operation evidence without losing history. | `/operations/:uuid` and linked feature pages; role-sensitive | UI-007, UI-014/015 | Archived/missing links remain truthful; sensitive recovery data is withheld. | Ready — UI-014 proves durable workflow links and UI-015 proves unavailable/missing identifiers plus rendered and network-payload disclosure boundaries. |
| BT-030 Operation disclosure; `TestOperationHistoryDisclosure` | Reader sees public summaries; Writer/Admin see only permitted recovery context. | `/operations`, `/operations/:uuid`; Reader/Writer/Admin | UI-007, UI-015 | Direct response/rendered page does not disclose fields forbidden to the role. | Ready — role-isolated network capture proves Reader redaction, Writer/Admin operational context, and universal exclusion of sensitive diagnostics. |
| BT-041 Snapshot/Backup administration contract | Inspect, create, and clean Backend-controlled recovery points. | `/admin/backups`; Admin | UI-010B/D, UI-026 | Arbitrary paths, unauthorized/cancelled/dismissed cleanup, corruption, and partial failure never claim full success. | Ready — Backend safety, explicit cancellation, non-dismissible cleanup review, interruption guidance, stale/replay, and truthful partial result evidence pass. |
| BT-042 protected database Restore orchestration | Restore a verified database recovery point after protective Snapshot and typed confirmation. | `/admin/restore`; Admin | UI-010C/D, UI-026 | Invalid/stale/duplicate/cancelled/dismissed Restore does not change the database; failure remains recoverable. | Ready — protected execution, typed confirmation, non-dismissible review, session invalidation, and post-Restore recovery pass. |
| BT-021 historical Workspace lifecycle; `test_workspace_workflow_acceptance` | Preserve historical lifecycle evidence without presenting archived rows as active UI work. | No active UI route; audit/migration evidence only | Backend evidence only; UI-001 exclusion | No active client can browse, edit, batch, or promote the archived collection. | Ready — intentional non-UI outcome established by MT-008 and the revised UI boundary. |
| Historical Workspace Review/Promotion contract; BT-031 and MT-008 | Historical materialization/archive remains traceable; it is not a reusable active Workspace. | No active UI route | Backend/migration evidence only | Archived rows cannot be reactivated through UI. | Ready — intentional non-UI outcome; not a future Workspace implementation. |
| BT-043–058 AI Collection Workspace and Work Dispatch | Admin filters available Albums; Backend atomically reserves one Album per active Worker Group; AI Worker submits dataset-versioned results for review, Promotion, release, and archive. | `/work-dispatch`, `/ai-reviews`; Admin, plus authenticated Worker API | UI-011A–F, UI-026–029 | Cross-Worker duplicate reservation, stale/interrupted dispatch, invalid or interrupted review, duplicate Promotion, premature release, and archived mutation obey the approved contracts. | Ready — durable workflow acceptance, reviewed-action lifecycle, per-item/version Review drafts, stale rebase/discard, refresh/restart recovery, interruption manifest, and a deterministic no-model drill proving the promoted value in `album.title` all pass. |

## Task-to-matrix ownership

| Task range | Matrix responsibility |
| --- | --- |
| UI-002–003 | Shared interaction contract and isolated evidence foundation for every browser-owned row. |
| UI-004A–C | Bootstrap and normal device connection lifecycle. |
| UI-005–010D | Permanent entities, Import, traceability, Repair, Quarantine, and Admin workflows. |
| UI-011A–D | Future AI Collection Workspace only. |
| UI-012–015 | Feature-level browser acceptance and role/disclosure evidence. |
| UI-016 | Gate composition, two-run rule, and published final classifications. |
| UI-022–028 | Controlling workflow Specification, audit remediation, and interruption-readiness enforcement. |
| UI-029 | Focused no-model AI dispatch-to-Promotion browser and database evidence. |

## Current gate evidence

`npm run test:ui-readiness` is the final UI-016 gate. Its explicit manifest
contains thirteen mandatory suites spanning foundations, authentication, Admin,
entities, Import, Operation history, Repair/Quarantine, disclosure, dispatch,
and AI review. It performs startup checks, enforces timeouts, uses isolated
fixtures, stops on failure, and reports each task, Specification, Backend
evidence, duration, and sanitized artifact location.

UI-016 previously completed two consecutive clean runs with no skips. Backend
`workflow-readiness` then passed twice (34 tests each), and the full Backend
regression passed once (751 tests). The smaller authenticated smoke scenario
remains part of, rather than a substitute for, this complete gate.

The 2026-08-13 Specification remediation completed UI-023–028. The upgraded
13-suite gate requires nine reasoned interruption dimensions, continues audit
execution after failures, and completed two consecutive clean runs. The
permission gate now distinguishes managed Registration Proof metadata from
plaintext secrets while retaining negative secret/hash/path assertions.
