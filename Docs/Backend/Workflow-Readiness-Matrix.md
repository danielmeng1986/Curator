# Backend Workflow Readiness Matrix

## Gate contract

Run from the repository root without starting the Web UI:

```bash
python3 tools/web_ui/tests/run_regression.py workflow-readiness
```

The command uses only disposable databases, filesystems, and an ephemeral
loopback HTTP server. A clean gate requires two consecutive successful runs.
`all` remains the complete Backend regression command.

| Classification | Meaning |
| --- | --- |
| Ready | The named scenario passes against isolated durable and filesystem/API boundaries. |
| Failing | The scenario runs and currently fails; its failure output is evidence and must not be skipped. |
| Not Implemented | A required specified surface or capability does not exist. |
| Blocked by Specification | The implementation cannot proceed without a resolved Specification decision. |

## Initial assessment

| Task / scenario | Controlling specification | Business outcome | Classification | Evidence / follow-up |
| --- | --- | --- | --- | --- |
| BT-019 import COPY, MOVE, database-only, preview | [Import Workflow](Specifications/Import-Workflow.md) | Canonical import persists truthful Operations and filesystem outcomes; preview is no-write. | Ready | `test_import_workflow_acceptance` |
| BT-020 failed import to verified repair | [Import Workflow](Specifications/Import-Workflow.md), [Repair Workflow](Specifications/Repair-Workflow.md) | Failed import remains `NeedsRepair`; linked repair verifies consistency without rewriting history. | Ready | `test_import_workflow_acceptance` |
| BT-021 workspace lifecycle | [Workspace Workflow](Specifications/Workspace-Workflow.md) | Active, Review, Closed and Archived states reject incompatible edits without side effects. | Ready | `test_workspace_workflow_acceptance` |
| Workspace Review field contract and promotion | [Workspace Workflow](Specifications/Workspace-Workflow.md) | Dataset-specific allowed Review changes and permanent promotion mapping. | Blocked by Specification | [BT-031](Tasks/BT-031-workspace-review-and-promotion-contract.md) |
| BT-022 repair policy, suppression, quarantine and restore | [Repair Workflow](Specifications/Repair-Workflow.md) | Only safe automatic rename proceeds; assisted/manual cases, suppression, quarantine and restore preserve safety. | Ready | `test_repair_policy_workflow_acceptance`, `test_quarantine_workflow_acceptance`, `test_repair_decision_workflow_acceptance` |
| BT-023 durable cross-workflow trail | [Operation Logging](Specifications/Operation-Logging.md), [Issue Management](Specifications/Issue-Management.md) | Import failure, repair, snapshot and authentication activities retain linked truthful records. | Ready | `test_traceability_workflow_acceptance` |
| Role-sensitive Operation-history diagnostics API | [Operation Logging](Specifications/Operation-Logging.md) | Reader receives public summaries; writer receives recovery context; sensitive diagnostics are withheld. | Ready | `TestOperationHistoryDisclosure` |
| BT-024 registration, approval and authenticated import entry | [Authentication](Specifications/Authentication.md), [API Contract](Specifications/API-Contract.md) | Loopback registration/approval issues one-time token; authorized writer enters `/api/v1/import/preview`; rejected request has no side effect. | Ready | `TestAuthenticatedApiWorkflow` |

This gate demonstrates only these listed workflows. It is not a production-readiness claim for performance, deployment, UI usability, or untested API surfaces.
