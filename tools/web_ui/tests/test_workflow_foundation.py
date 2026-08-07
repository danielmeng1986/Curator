"""Workflow acceptance-test foundation verification.

Controlling specifications: Testing Strategy / Workflow Tests and Sandbox
Environment; Operation Logging / Required record content.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox


class TestWorkflowAcceptanceFoundation(unittest.TestCase):
    """BT-018: isolated, observable, UI-independent workflow scenarios."""

    def _run_representative_scenario(self) -> tuple[str, str]:
        with WorkflowSandbox() as sandbox:
            source = sandbox.create_source_directory("album-source", ["cover.jpg"])
            sandbox.assert_path_exists(sandbox.source_root, "album-source/cover.jpg")
            sandbox.assert_path_missing(sandbox.archive_root, "A/Album")

            operation_service = svc.OperationService(
                repo.OperationRepository(sandbox.db_factory())
            )
            operation = operation_service.begin(
                "import",
                svc.OP_INITIATOR_CLI,
                summary="Representative isolated workflow",
                import_uuid="import-workflow-001",
                entity_uuid="album-workflow-001",
            )
            operation_service.succeed(operation["uuid"])
            issue = svc.IssueService(
                repo.IssueRepository(sandbox.db_factory())
            ).create(
                {
                    "category": "Validation",
                    "description": "Representative linked issue",
                    "affected_operation": operation["uuid"],
                    "source_workflow": "workflow-foundation",
                }
            )

            sandbox.assert_row_count("operation", 1)
            sandbox.assert_row_count("issue", 1)
            operation = sandbox.assert_operation(
                operation["uuid"],
                status="Succeeded",
                import_uuid="import-workflow-001",
                entity_uuid="album-workflow-001",
            )
            issue = sandbox.assert_issue(
                issue["uuid"],
                affected_operation=operation["uuid"],
            )
            return source.name, issue["source_workflow"]

    def test_bt018_representative_scenario_is_repeatable_from_clean_sandboxes(self):
        """Testing Strategy: the same scenario has equivalent durable outcomes."""
        first = self._run_representative_scenario()
        second = self._run_representative_scenario()

        self.assertEqual(first, second)

    def test_bt018_fixture_paths_cannot_escape_disposable_sandbox(self):
        """Testing Strategy: fixtures cannot target production-like paths."""
        with WorkflowSandbox() as sandbox:
            with self.assertRaisesRegex(ValueError, "relative path"):
                sandbox.create_source_directory("/outside-workflow-sandbox")
            with self.assertRaisesRegex(ValueError, "escapes"):
                sandbox.create_source_directory("../outside-workflow-sandbox")
