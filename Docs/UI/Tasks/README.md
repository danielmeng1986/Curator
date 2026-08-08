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
If the UI plan is stale—for example, where it still mentions the retired
historical `workspace_album` collection or excludes the now-required
authentication model—the specification task must resolve that conflict before
implementation begins.

Browser acceptance tests complement, and never replace, Backend workflow
acceptance tests. They must use disposable database, filesystem, token,
snapshot, archive, and output resources.

## Task index

| Task | Outcome | Status |
| --- | --- | --- |
| [UI-001](UI-001-establish-workflow-coverage-matrix.md) | Controlling UI workflow and readiness matrix | Proposed |
| [UI-002](UI-002-standardize-permissions-errors-and-feedback.md) | Shared permissions, errors, and feedback | Proposed |
| [UI-003](UI-003-establish-browser-workflow-fixtures.md) | Disposable browser workflow fixtures | Proposed |
| [UI-004A](UI-004A-command-line-admin-bootstrap.md) | Supported initial administrator CLI bootstrap | Proposed |
| [UI-004B](UI-004B-loopback-admin-ui-bootstrap.md) | One-time loopback administrator UI bootstrap | Proposed |
| [UI-004C](UI-004C-token-connection-lifecycle-ui.md) | Connection and token lifecycle UI | Proposed |
| [UI-005](UI-005-adapt-entity-management-ui.md) | Permanent entity management adaptation | Proposed |
| [UI-006](UI-006-adapt-import-workflow-ui.md) | Import preview and execution UI | Proposed |
| [UI-007](UI-007-add-operation-history-ui.md) | Operation history and traceability UI | Proposed |
| [UI-008](UI-008-add-issue-and-repair-decision-ui.md) | Issue and Repair decision UI | Proposed |
| [UI-009](UI-009-add-quarantine-and-restore-ui.md) | Quarantine and item restore UI | Proposed |
| [UI-010](UI-010-establish-admin-center.md) | Administrator Center shell and policy | Proposed |
| [UI-010A](UI-010A-administer-devices-and-tokens.md) | Device registration and token administration | Proposed |
| [UI-010B](UI-010B-administer-backups-and-snapshots.md) | Backup and Snapshot administration | Completed |
| [UI-010C](UI-010C-administer-database-restore.md) | Database restore administration | Completed |
| [UI-010D](UI-010D-admin-workflow-browser-acceptance.md) | Administrator workflow browser acceptance | Completed |
| [UI-010E](UI-010E-administer-digital-asset-trash.md) | Digital Asset Trash review, restore, and purge | Blocked |
| [UI-011A](UI-011A-specify-ai-collection-workspace.md) | AI Collection Workspace product/data contract | Proposed |
| [UI-011B](UI-011B-specify-workspace-review-state-machine.md) | Stable review state machine and read model | Proposed |
| [UI-011C](UI-011C-build-workspace-review-ui.md) | Dataset-adaptable Workspace review UI | Proposed |
| [UI-011D](UI-011D-workspace-browser-acceptance.md) | Workspace browser acceptance | Proposed |
| [UI-012](UI-012-entity-management-browser-acceptance.md) | Entity-management browser acceptance | Proposed |
| [UI-013](UI-013-import-browser-acceptance.md) | Import browser acceptance | Proposed |
| [UI-014](UI-014-repair-and-quarantine-browser-acceptance.md) | Repair, Issue, and Quarantine browser acceptance | Proposed |
| [UI-015](UI-015-permission-disclosure-browser-acceptance.md) | Role and diagnostic-disclosure acceptance | Proposed |
| [UI-016](UI-016-establish-ui-workflow-readiness-gate.md) | Complete UI workflow readiness gate | Proposed |

## Dependency outline

`UI-001` controls coverage. `UI-002` and `UI-003` establish shared runtime and
test foundations. Feature tasks `UI-004*` through `UI-011*` build on those
foundations. Acceptance tasks `UI-012` through `UI-015` verify the feature
workflows, and `UI-016` composes them into the final readiness gate.
