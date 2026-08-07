"""BT-021 workspace lifecycle workflow acceptance scenarios.

Controlling specification: Workspace Workflow / lifecycle state machine,
controlled Review modifications, and validation and error handling.
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


class TestWorkspaceLifecycleWorkflowAcceptance(unittest.TestCase):
    """BT-021: lifecycle changes and state-incompatible edit rejection."""

    def setUp(self):
        self.sandbox = WorkflowSandbox()
        self.snapshot_paths: list[Path] = []
        self.backup_log: list[dict] = []
        self.service = svc.WorkspaceAlbumService(
            repo.WorkspaceAlbumRepository(self.sandbox.db_factory()),
            snapshot_fn=self._create_snapshot,
            backup_log_fn=self.backup_log.append,
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

    def _workspace_state(self, workspace_id: int) -> tuple[str, str | None]:
        conn = self.sandbox.connect()
        try:
            row = conn.execute(
                "SELECT lifecycle_state, remark FROM workspace_album WHERE id = ?",
                (workspace_id,),
            ).fetchone()
        finally:
            conn.close()
        return row["lifecycle_state"], row["remark"]

    def test_bt021_lifecycle_transitions_persist_and_keep_history_read_only(self):
        """Workspace Workflow: Active → Review → Closed → Archived / Retired."""
        workspace = self.service.create(
            {"studio_name": "Studio", "album_name": "Album", "remark": "initial"}
        )
        workspace_id = workspace["id"]
        self.assertEqual(self._workspace_state(workspace_id)[0], svc.LIFECYCLE_ACTIVE)

        self.service.submit_for_review(workspace_id)
        self.assertEqual(self._workspace_state(workspace_id)[0], svc.LIFECYCLE_REVIEW)
        # No workspace_album-specific Review editing contract exists, so the
        # general edit boundary remains closed in Review.
        with self.assertRaises(svc.ServiceConflict):
            self.service.update(workspace_id, {"remark": "uncontrolled review edit"})
        self.assertEqual(self._workspace_state(workspace_id)[1], "initial")

        self.service.close(workspace_id)
        self.assertEqual(self._workspace_state(workspace_id)[0], svc.LIFECYCLE_CLOSED)
        with self.assertRaises(svc.ServiceConflict):
            self.service.update(workspace_id, {"remark": "closed edit"})
        self.assertEqual(self._workspace_state(workspace_id)[1], "initial")

        self.service.archive(workspace_id)
        self.assertEqual(
            self._workspace_state(workspace_id)[0], svc.LIFECYCLE_ARCHIVED_RETIRED
        )
        with self.assertRaises(svc.ServiceConflict):
            self.service.batch_update([workspace_id], {"remark": "archived edit"})
        self.assertEqual(self._workspace_state(workspace_id)[1], "initial")
        self.assertEqual(self.snapshot_paths, [])
        self.assertEqual(self.backup_log, [])

    def test_bt021_invalid_transition_has_no_persisted_side_effect(self):
        """Workspace Workflow: an invalid transition leaves state unchanged."""
        workspace = self.service.create({"studio_name": "Studio", "album_name": "Album"})

        with self.assertRaises(svc.ServiceConflict):
            self.service.close(workspace["id"])

        self.assertEqual(self._workspace_state(workspace["id"])[0], svc.LIFECYCLE_ACTIVE)
