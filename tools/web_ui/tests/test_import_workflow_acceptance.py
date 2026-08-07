"""BT-019 import happy-path workflow acceptance scenarios.

Controlling specifications: Import Workflow / staged workflow, confirmation,
and Import Action; Operation Logging / import execution requirements.
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


class TestImportHappyPathWorkflowAcceptance(unittest.TestCase):
    """BT-019: confirmed Album import through real service boundaries."""

    def setUp(self):
        self.sandbox = WorkflowSandbox()
        self.backup_log: list[dict] = []
        self.change_log: list[dict] = []
        self.snapshot_paths: list[Path] = []
        self.service = svc.ImportService(
            repo.ImportRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
            change_log_fn=self.change_log.append,
            operation_service=svc.OperationService(
                repo.OperationRepository(self.sandbox.db_factory())
            ),
        )

    def tearDown(self):
        self.sandbox.close()

    def _create_snapshot(self, reason: str) -> Path:
        snapshot = self.sandbox.path_under(
            self.sandbox.snapshot_root, f"{reason}-{len(self.snapshot_paths)}.db"
        )
        snapshot.touch()
        self.snapshot_paths.append(snapshot)
        return snapshot

    @staticmethod
    def _candidate(source_path: Path | str = "") -> dict:
        return {
            "model_name": "Alice",
            "studio_name": "Studio One",
            "album_name": "Summer Set",
            "source_path": str(source_path),
        }

    def _preview_then_execute(self, action: str, source_path: Path | str = "") -> dict:
        candidate = self._candidate(source_path)
        preview = self.service.preview(
            [candidate], str(self.sandbox.archive_root), "Default Studio"
        )
        self.assertTrue(preview["items"][0]["can_import"])
        return self.service.execute(
            [candidate],
            str(self.sandbox.archive_root),
            "Default Studio",
            import_action=action,
        )

    def _assert_successful_execution(self, result: dict, expected_action: str) -> None:
        item = result["results"][0]
        self.assertTrue(item["ok"])
        self.assertFalse(item["skipped"])
        self.assertFalse(item["needs_repair"])
        self.assertEqual(item["effective_action"], expected_action)
        self.assertEqual(result["summary"], {
            "total": 1,
            "created": 1,
            "skipped": 0,
            "errors": 0,
            "needs_repair": 0,
        })
        self.sandbox.assert_row_count("album", 1)
        self.assertEqual(len(self.snapshot_paths), 1)
        self.assertTrue(self.snapshot_paths[0].is_file())
        self.assertEqual(self.backup_log[0]["reason"], "import")
        self.assertTrue(self.change_log[0]["success"])

        # Import Workflow and Operation Logging require a durable, linked
        # outcome.  A JSONL-style change-log entry is not a substitute.
        self.sandbox.assert_row_count("operation", 1)
        operation = self.sandbox.assert_operation_for_import(
            result["import_uuid"],
            operation_type="import",
            status="Succeeded",
            import_uuid=result["import_uuid"],
        )
        self.assertNotEqual(operation["uuid"], result["import_uuid"])

    def test_bt019_preview_has_no_production_persistence_snapshot_or_operation(self):
        """Import Workflow: preview is a no-write stage before confirmation."""
        preview = self.service.preview(
            [self._candidate()], str(self.sandbox.archive_root), "Default Studio"
        )

        self.assertTrue(preview["items"][0]["can_import"])
        self.sandbox.assert_row_count("album", 0)
        self.sandbox.assert_row_count("operation", 0)
        self.assertEqual(self.snapshot_paths, [])
        self.assertEqual(self.change_log, [])

    def test_bt019_database_only_persists_without_filesystem_mutation(self):
        """Import Workflow: DATABASE_ONLY persists identity and skips filesystem work."""
        source = self.sandbox.create_source_directory("database-only", ["cover.jpg"])
        result = self._preview_then_execute(svc.IMPORT_ACTION_DATABASE_ONLY, source)

        item = result["results"][0]
        self._assert_successful_execution(result, svc.IMPORT_ACTION_DATABASE_ONLY)
        self.assertTrue(source.is_dir())
        self.sandbox.assert_path_missing(self.sandbox.archive_root, item["expected_path"])

    def test_bt019_copy_preserves_source_and_creates_canonical_destination(self):
        """Import Workflow: COPY preserves source and copies into canonical path."""
        source = self.sandbox.create_source_directory("copy-source", ["cover.jpg"])
        result = self._preview_then_execute(svc.IMPORT_ACTION_COPY, source)

        item = result["results"][0]
        self._assert_successful_execution(result, svc.IMPORT_ACTION_COPY)
        self.assertTrue(source.is_dir())
        self.sandbox.assert_path_exists(
            self.sandbox.archive_root, f"{item['expected_path']}/cover.jpg"
        )

    def test_bt019_move_removes_source_and_creates_canonical_destination(self):
        """Import Workflow: MOVE relocates source into canonical path."""
        source = self.sandbox.create_source_directory("move-source", ["cover.jpg"])
        result = self._preview_then_execute(svc.IMPORT_ACTION_MOVE, source)

        item = result["results"][0]
        self._assert_successful_execution(result, svc.IMPORT_ACTION_MOVE)
        self.assertFalse(source.exists())
        self.sandbox.assert_path_exists(
            self.sandbox.archive_root, f"{item['expected_path']}/cover.jpg"
        )

    def test_bt019_source_at_canonical_destination_uses_database_only(self):
        """Import Workflow: an already-canonical source performs no redundant move."""
        expected_path = svc.build_archive_path("Alice", "Studio One", "Summer Set")
        source = self.sandbox.path_under(self.sandbox.archive_root, expected_path)
        source.mkdir(parents=True)
        (source / "cover.jpg").touch()

        result = self._preview_then_execute(svc.IMPORT_ACTION_MOVE, source)

        item = result["results"][0]
        self.assertTrue(item["ok"])
        self.assertEqual(item["effective_action"], svc.IMPORT_ACTION_DATABASE_ONLY)
        self.sandbox.assert_row_count("album", 1)
        self.assertTrue((source / "cover.jpg").is_file())
