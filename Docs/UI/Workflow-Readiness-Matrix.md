# UI Workflow Readiness Matrix

## Gate contract

This matrix maps supported Backend workflow evidence to user-facing UI
outcomes. A Backend workflow can be Ready while its UI is Not Implemented; the
browser layer verifies client integration and does not repeat every Service
rule.

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
| BT-024 authenticated API workflow; `TestAuthenticatedApiWorkflow` | Connect an approved device and enter protected UI safely. | Connection dialog; Reader/Writer/Admin | UI-004C, UI-015 | Missing, invalid, expired, revoked, and insufficient-scope Token makes no business mutation. | Not Implemented — current UI has Token storage and a smoke path, but no complete lifecycle/principal UI. |
| Authentication registration/approval services and tests | Establish the first Admin, then review registrations, renewals, elevation, and revocation. | First-run bootstrap; `/admin/devices`; Admin | UI-004A/B, UI-010A/D | Wrong/expired/replayed bootstrap, self-approval, last-Admin revocation, and unauthorized management preserve auth state. | Blocked by Specification — bootstrap, recovery, last-Admin, and authenticated management contracts require approval; current loopback management is not the target UI contract. |
| Entity repository/service/API regression | Manage permanent Albums, Models, Studios, Statuses, Photos, and relationships. | `/albums`, `/models`, `/studios`, `/statuses`; Reader/Writer | UI-005, UI-012 | Validation, duplicate/self relation, reference-protected delete, and Reader writes preserve prior state. | Not Implemented — pages exist, but full contract adaptation and browser evidence are incomplete. |
| BT-019 Import COPY, MOVE, database-only, preview; `test_import_workflow_acceptance` | Review zero-write preview and execute the selected filesystem/database mode with truthful results. | `/import/albums`; Writer | UI-006, UI-013 | Invalid/collision/stale/cancelled/repeated requests have no unintended mutation; partial failure matches durable/filesystem outcome. | Not Implemented — basic page/API exists; complete modes, reviewed-preview identity, traceability, and browser evidence are incomplete. |
| BT-020 failed Import to verified Repair; `test_import_workflow_acceptance` | See `NeedsRepair`, follow its Issue/Repair, make an allowed decision, and verify completion. | Import result → `/issues/:uuid`; Writer/Admin | UI-006–008, UI-014 | Client cannot force unsafe policy; invalid/stale/repeated decisions preserve state. | Not Implemented — Backend workflow is Ready, but Issue/Repair UI APIs and pages are absent. |
| BT-022 Repair policy/suppression; `test_repair_policy_workflow_acceptance`, `test_repair_decision_workflow_acceptance` | Review automatic/assisted/manual classification; accept, reject, confirm, or suppress as authorized. | `/issues`, `/issues/:uuid`; Writer/Admin | UI-008, UI-014 | Unsafe automatic rename, missing confirmation, unauthorized suppression, and invalid transition have zero unintended side effects. | Not Implemented — UI-facing read/decision endpoints and pages are absent. |
| BT-022 Quarantine/Restore; `test_quarantine_workflow_acceptance` | Quarantine and restore individual filesystem items with verified traceability. | `/admin/quarantine`; Admin | UI-009, UI-014 | Cancel, collision, missing item, replay, and non-Admin request preserve filesystem/durable state. | Not Implemented — Service evidence exists; Admin API/read model and UI are absent. |
| BT-023 cross-workflow trail; `test_traceability_workflow_acceptance` | Navigate Import → Issue → Repair → Snapshot/Operation evidence without losing history. | `/operations/:uuid` and linked feature pages; role-sensitive | UI-007, UI-014/015 | Archived/missing links remain truthful; sensitive recovery data is withheld. | Not Implemented — Operation list/detail APIs exist, but pages and several linked resource APIs do not. |
| BT-030 Operation disclosure; `TestOperationHistoryDisclosure` | Reader sees public summaries; Writer/Admin see only permitted recovery context. | `/operations`, `/operations/:uuid`; Reader/Writer/Admin | UI-007, UI-015 | Direct response/rendered page does not disclose fields forbidden to the role. | Not Implemented — Backend API is Ready; UI route and browser disclosure evidence are absent. |
| Snapshot/Backup service and API regression | Inspect/create/clean Backend-controlled recovery points. | `/admin/recovery`; Admin | UI-010B/D | Arbitrary paths, unauthorized/cancelled cleanup, corruption, and partial failure never claim full success. | Not Implemented — legacy handlers exist; target authenticated Admin read/action contract and UI are incomplete. |
| Snapshot decision/restore service and API regression | Restore a verified database recovery point after protective Snapshot and confirmation. | `/admin/recovery/restore`; Admin | UI-010C/D | Invalid/stale/duplicate/cancelled Restore does not change the database; failure remains recoverable. | Blocked by Specification — confirmation strength, interruption, recovery, and post-Restore session behavior require approval. |
| BT-021 historical Workspace lifecycle; `test_workspace_workflow_acceptance` | Preserve historical lifecycle evidence without presenting archived rows as active UI work. | No active UI route; audit/migration evidence only | Backend evidence only; UI-001 exclusion | No active client can browse, edit, batch, or promote the archived collection. | Ready — intentional non-UI outcome established by MT-008 and the revised UI boundary. |
| Historical Workspace Review/Promotion contract; BT-031 and MT-008 | Historical materialization/archive remains traceable; it is not a reusable active Workspace. | No active UI route | Backend/migration evidence only | Archived rows cannot be reactivated through UI. | Ready — intentional non-UI outcome; not a future Workspace implementation. |
| Future AI Collection Workspace | AI Worker submits dataset-versioned results for human review, decision, Promotion, and archive through stable review fields. | Future `/workspace`, `/workspace/:uuid`; Writer/Admin as specified | UI-011A–D | Invalid/stale transitions, Reject, duplicate Promotion, and archived mutation obey the approved contract. | Blocked by Specification — UI-011A/B must define the dataset and stable state/read model before Backend or UI work. |

## Task-to-matrix ownership

| Task range | Matrix responsibility |
| --- | --- |
| UI-002–003 | Shared interaction contract and isolated evidence foundation for every browser-owned row. |
| UI-004A–C | Bootstrap and normal device connection lifecycle. |
| UI-005–010D | Permanent entities, Import, traceability, Repair, Quarantine, and Admin workflows. |
| UI-011A–D | Future AI Collection Workspace only. |
| UI-012–015 | Feature-level browser acceptance and role/disclosure evidence. |
| UI-016 | Gate composition, two-run rule, and published final classifications. |

## Current gate evidence

The existing `apps/web/tests/browser_workflow_acceptance.mjs` remains a smoke
test: it proves missing-token presentation, connection with an approved Writer
Token, Album access, and one rejected Admin request with unchanged Album count.
It does not make the rows above Ready unless their named UI task and durable
browser evidence are complete.
