# Curator UI Tasks

## Purpose

This directory is the planning layer for Curator Web UI work. UI tasks are
kept separate from Backend tasks (`BT-*`) and cross-project migration tasks
(`MT-*`). They define reviewable UI specification, implementation, and
browser-workflow acceptance units without changing Backend contracts silently.

## Naming and status

Task filenames use `UI-<three-digit-sequence>-<short-kebab-case-title>.md`.
Closely related follow-up tasks may use a stable letter suffix, for example
`UI-010A`. IDs are permanent and are not reused after cancellation or
supersession. Status is one of `Proposed`, `Ready`, `In Progress`, `Blocked`,
`Complete`, or `Superseded`.

## Readiness rule

A UI task is `Ready` only when its controlling UI and Backend contracts agree.
If the current UI description is stale—for example, where it still mentions the retired
historical `workspace_album` collection or excludes the now-required
authentication model—the specification task must resolve that conflict before
implementation begins.

Browser acceptance tests complement, and never replace, Backend workflow
acceptance tests. They must use disposable database, filesystem, token,
snapshot, archive, and output resources.

## Task index

| Task | Outcome | Status |
| --- | --- | --- |
| [UI-001](UI-001-establish-workflow-coverage-matrix.md) | Controlling UI workflow and readiness matrix | Complete |
| [UI-002](UI-002-standardize-permissions-errors-and-feedback.md) | Shared permissions, errors, and feedback | Complete |
| [UI-003](UI-003-establish-browser-workflow-fixtures.md) | Disposable browser workflow fixtures | Complete |
| [UI-004A](UI-004A-command-line-admin-bootstrap.md) | Supported initial administrator CLI bootstrap | Complete |
| [UI-004B](UI-004B-loopback-admin-ui-bootstrap.md) | One-time loopback administrator UI bootstrap | Complete |
| [UI-004C](UI-004C-token-connection-lifecycle-ui.md) | Connection and token lifecycle UI | Complete |
| [UI-005](UI-005-adapt-entity-management-ui.md) | Permanent entity management adaptation | Complete |
| [UI-006](UI-006-adapt-import-workflow-ui.md) | Import preview and execution UI | Complete |
| [UI-007](UI-007-add-operation-history-ui.md) | Operation history and traceability UI | Complete |
| [UI-008](UI-008-add-issue-and-repair-decision-ui.md) | Issue and Repair decision UI | Complete |
| [UI-009](UI-009-add-quarantine-and-restore-ui.md) | Quarantine and item restore UI | Complete |
| [UI-010](UI-010-establish-admin-center.md) | Administrator Center shell and policy | Complete |
| [UI-010A](UI-010A-administer-devices-and-tokens.md) | Device registration and token administration | Complete |
| [UI-010B](UI-010B-administer-backups-and-snapshots.md) | Backup and Snapshot administration | Complete |
| [UI-010C](UI-010C-administer-database-restore.md) | Database restore administration | Complete |
| [UI-010D](UI-010D-admin-workflow-browser-acceptance.md) | Administrator workflow browser acceptance | Complete |
| [UI-010E](UI-010E-administer-digital-asset-trash.md) | Digital Asset Trash review, restore, and purge | Blocked |
| [UI-011A](UI-011A-specify-ai-collection-workspace.md) | AI Collection Workspace product/data contract | Complete |
| [UI-011B](UI-011B-specify-workspace-review-state-machine.md) | Stable review state machine and read model | Complete |
| [UI-011C](UI-011C-build-workspace-review-ui.md) | Dataset-adaptable Workspace review UI | Complete |
| [UI-011D](UI-011D-workspace-browser-acceptance.md) | Workspace browser acceptance | Complete |
| [UI-011E](UI-011E-build-filtered-album-work-dispatch-ui.md) | Filtered Admin Album work dispatch console | Complete |
| [UI-011F](UI-011F-work-dispatch-browser-acceptance.md) | Album-exclusive dispatch browser acceptance | Complete |
| [UI-012](UI-012-entity-management-browser-acceptance.md) | Entity-management browser acceptance | Complete |
| [UI-013](UI-013-import-browser-acceptance.md) | Import browser acceptance | Complete |
| [UI-014](UI-014-repair-and-quarantine-browser-acceptance.md) | Repair, Issue, and Quarantine browser acceptance | Complete |
| [UI-015](UI-015-permission-disclosure-browser-acceptance.md) | Role and diagnostic-disclosure acceptance | Complete |
| [UI-016](UI-016-establish-ui-workflow-readiness-gate.md) | Complete UI workflow readiness gate | Complete |
| [UI-017](UI-017-establish-playwright-browser-acceptance.md) | Reproducible real-browser acceptance infrastructure | Complete |
| [UI-018](UI-018-prevent-stale-album-list-refresh-after-navigation.md) | Stable Album detail after list navigation | Complete |
| [UI-019](UI-019-request-device-access.md) | Reader/Writer access request and automatic connection | Complete |
| [UI-020](UI-020-manage-registration-proof.md) | Admin Registration Proof lifecycle UI | Complete |
| [UI-021](UI-021-device-enrollment-browser-acceptance.md) | Multi-browser device enrollment acceptance | Complete |
| [UI-022](UI-022-establish-ui-workflow-specification.md) | Controlling workflow, interruption, recovery, and upgrade specification | Complete |
| [UI-023](UI-023-correct-permission-disclosure-gate.md) | Schema-aware credential disclosure readiness gate | Complete |
| [UI-024](UI-024-preserve-entity-editing-context.md) | Entity draft and list-navigation continuity | Complete |
| [UI-025](UI-025-resume-import-workflow.md) | Resumable Import compose, review, and result workflow | Complete |
| [UI-026](UI-026-standardize-reviewed-action-lifecycle.md) | Explicit lifecycle for material Preview and confirmation | Complete |
| [UI-027](UI-027-persist-ai-review-drafts.md) | Interruption-safe human AI Review drafts | Complete |
| [UI-028](UI-028-enforce-workflow-interruption-readiness.md) | Specification interruption matrix in the final readiness gate | Complete |
| [UI-029](UI-029-simulated-ai-promotion-workflow-drill.md) | No-model dispatch, Worker result, Review, and Album Promotion drill | Complete |
| [UI-030](UI-030-expose-ai-configuration-and-run-progress.md) | Model configuration summaries and per-Album run progress | Complete |
| [UI-031](UI-031-administer-ai-model-configurations.md) | Administrator AI Model Configuration management | Complete |
| [UI-032](UI-032-complete-work-dispatch-filtering-and-pagination.md) | Status-centered Dispatch filtering and bounded pagination | Complete |
| [UI-033](UI-033-streamline-ai-review-and-live-dispatch-progress.md) | Fast sequential Album review and automatically refreshed run progress | Complete |
| [UI-034](UI-034-live-review-and-ephemeral-evidence-preview.md) | Live AI Review state and ephemeral lazy-loaded evidence preview | Complete |

## Dependency outline

`UI-001` controls coverage. `UI-002` and `UI-003` establish shared runtime and
test foundations. Feature tasks `UI-004*` through `UI-011*` build on those
foundations. Acceptance tasks `UI-012` through `UI-015` verify the feature
workflows, and `UI-016` composes them into the final readiness gate.

For AI Workspace delivery, UI-011A/B precede dispatch implementation UI-011E.
UI-011F proves the dispatch boundary; UI-011C/D consume the resulting Groups
and Work Items for review and end-to-end acceptance.

UI-017 formalizes Playwright as the real-browser acceptance layer. It preserves
the faster Backend, API, and client-contract layers and provides the shared
runner used by feature and release browser gates.

UI-022 makes the UI Specification controlling for all subsequent feature and
acceptance work. New or materially changed workflows must define their complete
state, interruption, persistence, recovery, and upgrade behavior before they
can be classified Ready.

The 2026-08-13 audit created UI-023–028. UI-023 restores accurate gate
semantics; UI-024–027 close product workflow gaps; UI-028 makes their
interruption evidence mandatory in the final readiness gate.

UI-029 adds a focused one-Album drill proving the production orchestration and
permanent database outcome with deterministic Worker payloads and no AI model.

UI-030 makes dispatch choices inspectable before confirmation and projects each
Album/configuration run independently in Active, History, and Group detail.

UI-031 closes the first-run configuration gap by exposing the existing managed
model configuration contract to Administrators. UI-032 completes the Dispatch
list behavior promised by UI-011E by wiring the existing Status, Studio, Model,
and pagination contracts into the browser workflow.

UI-033 optimizes the completed end-to-end workflow for a large Review Queue. It
keeps one-Album audit and Promotion boundaries, replaces repeated name entry
only after the Backend confirmation contract is amended, adds stable next-review
navigation, and uses bounded native-JavaScript polling for live Dispatch progress.
