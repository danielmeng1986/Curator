"""BT-019 import happy-path workflow acceptance scenarios.

Controlling specifications: Import Workflow / staged workflow, confirmation,
and Import Action; Operation Logging / import execution requirements.
"""

from __future__ import annotations

import sys
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.operation_service = svc.OperationService(
            repo.OperationRepository(self.sandbox.db_factory())
        )
        self.service = svc.ImportService(
            repo.ImportRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
            change_log_fn=self.change_log.append,
            operation_service=self.operation_service,
        )
        self.repair_service = svc.RepairService(
            repo.RepairRepository(self.sandbox.db_factory()),
            repo.IssueRepository(self.sandbox.db_factory()),
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

    def test_bt036_changed_source_rejects_reviewed_preview_without_side_effect(self):
        source = self.sandbox.create_source_directory("stale-source", ["cover.jpg"])
        strict = svc.ImportService(
            repo.ImportRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
            change_log_fn=self.change_log.append,
            operation_service=self.operation_service,
            preview_secret=b"bt036-preview-secret",
        )
        preview = strict.preview(
            [self._candidate(source)], str(self.sandbox.archive_root), "Default Studio",
            import_action=svc.IMPORT_ACTION_MOVE,
        )
        (source / "added-after-preview.jpg").touch()
        with self.assertRaises(svc.ServiceConflict) as stale:
            strict.execute_preview(
                preview["preview_token"], str(self.sandbox.archive_root), "Default Studio"
            )
        self.assertEqual(stale.exception.code, "IMPORT_PREVIEW_STALE")
        self.sandbox.assert_row_count("album", 0)
        self.sandbox.assert_row_count("operation", 0)
        self.assertTrue(source.is_dir())
        self.assertEqual(self.snapshot_paths, [])

    def test_bt036_preview_is_single_use_and_binds_database_only_action(self):
        strict = svc.ImportService(
            repo.ImportRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
            change_log_fn=self.change_log.append,
            operation_service=self.operation_service,
            preview_secret=b"bt036-preview-secret",
        )
        preview = strict.preview(
            [self._candidate()], str(self.sandbox.archive_root), "Default Studio",
            import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
        )
        result = strict.execute_preview(
            preview["preview_token"], str(self.sandbox.archive_root), "Default Studio"
        )
        self.assertEqual(result["results"][0]["effective_action"], svc.IMPORT_ACTION_DATABASE_ONLY)
        with self.assertRaises(svc.ServiceConflict) as replay:
            strict.execute_preview(
                preview["preview_token"], str(self.sandbox.archive_root), "Default Studio"
            )
        self.assertEqual(replay.exception.code, "IMPORT_PREVIEW_REPLAYED")
        self.sandbox.assert_row_count("album", 1)
        self.sandbox.assert_row_count("operation", 1)

    def test_bt036_expired_preview_is_rejected_before_claim_or_operation(self):
        strict = svc.ImportService(
            repo.ImportRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
            change_log_fn=self.change_log.append,
            operation_service=self.operation_service,
            preview_secret=b"bt036-preview-secret",
        )
        preview = strict.preview(
            [self._candidate()], str(self.sandbox.archive_root), "Default Studio",
            import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
        )
        payload = strict._read_import_preview(preview["preview_token"])
        payload["expires_at"] = "2000-01-01T00:00:00+00:00"
        expired_token = strict._sign_import_preview(payload)
        with self.assertRaises(svc.ServiceConflict) as expired:
            strict.execute_preview(
                expired_token, str(self.sandbox.archive_root), "Default Studio"
            )
        self.assertEqual(expired.exception.code, "IMPORT_PREVIEW_EXPIRED")
        self.sandbox.assert_row_count("album", 0)
        self.sandbox.assert_row_count("operation", 0)

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

    def test_bt020_import_filesystem_failure_repairs_to_verified_consistency(self):
        """Import/Repair: a failed MOVE keeps history and repairs by verification."""
        source = self.sandbox.create_source_directory("repair-source", ["cover.jpg"])
        candidate = self._candidate(source)
        preview = self.service.preview(
            [candidate], str(self.sandbox.archive_root), "Default Studio"
        )
        self.assertTrue(preview["items"][0]["can_import"])

        # The failure is injected at the filesystem adapter boundary after the
        # repository has persisted the Album and before filesystem verification.
        with patch.object(svc.shutil, "move", side_effect=OSError("injected move failure")):
            failed_import = self.service.execute(
                [candidate],
                str(self.sandbox.archive_root),
                "Default Studio",
                import_action=svc.IMPORT_ACTION_MOVE,
            )

        item = failed_import["results"][0]
        self.assertTrue(item["needs_repair"])
        self.assertFalse(item["ok"])
        original_operation = self.sandbox.assert_operation_for_import(
            failed_import["import_uuid"],
            status=svc.OP_STATUS_NEEDS_REPAIR,
            error_category="filesystem",
            error_code="filesystem.write-failed",
            repair_state="NeedsRepair",
        )
        conn = self.sandbox.connect()
        try:
            album = conn.execute(
                "SELECT uuid, path FROM album WHERE id = ?", (item["album_id"],)
            ).fetchone()
        finally:
            conn.close()

        handoff = self.repair_service.detect(
            original_operation["uuid"],
            album["uuid"],
            album["path"],
            category=svc.REPAIR_CATEGORY_AUTOMATIC,
            failure_reason=item["error"],
        )
        repair = handoff["repair"]
        issue = handoff["issue"]
        self.assertEqual(repair["operation_uuid"], original_operation["uuid"])
        self.assertEqual(issue["affected_operation"], original_operation["uuid"])

        repair_operation = self.operation_service.begin(
            "repair",
            svc.OP_INITIATOR_CLI,
            repair_uuid=repair["uuid"],
            related_operation_uuid=original_operation["uuid"],
            entity_uuid=album["uuid"],
            summary="Retry failed import move.",
        )
        destination = self.sandbox.path_under(self.sandbox.archive_root, album["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        self.repair_service.start_repair(repair["uuid"])
        self.repair_service.complete_action(repair["uuid"])
        resolved = self.repair_service.verify(
            repair["uuid"], passed=True, result="Canonical path and directory verified."
        )
        self.operation_service.succeed(
            repair_operation["uuid"], summary="Import filesystem repair verified."
        )

        self.assertEqual(resolved["state"], svc.REPAIR_STATE_RESOLVED)
        self.sandbox.assert_path_exists(
            self.sandbox.archive_root, f"{album['path']}/cover.jpg"
        )
        self.sandbox.assert_operation(
            original_operation["uuid"], status=svc.OP_STATUS_NEEDS_REPAIR
        )
        self.sandbox.assert_operation(
            repair_operation["uuid"],
            status=svc.OP_STATUS_SUCCEEDED,
            repair_uuid=repair["uuid"],
            related_operation_uuid=original_operation["uuid"],
        )
