"""BT-029 quarantine and restore safety acceptance scenarios."""
from __future__ import annotations
import unittest
import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox

class TestQuarantineWorkflowAcceptance(unittest.TestCase):
    def setUp(self):
        self.box = WorkflowSandbox(); factory = self.box.db_factory(); self.audit = []; self.snapshots = []
        self.service = svc.QuarantineService(repo.QuarantineRepository(factory), svc.OperationService(repo.OperationRepository(factory)), self.box.archive_root, self.box.quarantine_root, lambda reason: self.snapshots.append(reason) or self.box.snapshot_root / f"{reason}.db", self.audit.append)
    def tearDown(self): self.box.close()
    def _archive_dir(self, relative):
        p = self.box.path_under(self.box.archive_root, relative); p.mkdir(parents=True); (p / "photo.jpg").touch(); return p
    def test_bt029_quarantine_is_admin_only_and_preserves_directory_metadata(self):
        self._archive_dir("A/Alice/p/Studio/Conflict")
        with self.assertRaises(svc.ServiceConflict): self.service.quarantine("A/Alice/p/Studio/Conflict", repair_uuid="repair-1", reason="collision", actor_role="writer")
        item = self.service.quarantine("A/Alice/p/Studio/Conflict", repair_uuid="repair-1", reason="collision", actor_role="admin")
        self.box.assert_path_missing(self.box.archive_root, "A/Alice/p/Studio/Conflict")
        self.box.assert_path_exists(self.box.quarantine_root, f"{item['uuid']}/photo.jpg")
        self.assertEqual("A/Alice/p/Studio/Conflict", item["original_path"]); self.assertIn("photo.jpg", item["inventory"])
        with self.assertRaises(svc.ServiceConflict): self.service.list_items(actor_role="writer")
        self.assertEqual(1, len(self.service.list_items(actor_role="admin")))
    def test_bt029_restore_never_overwrites_and_requires_snapshot(self):
        self._archive_dir("A/Alice/p/Studio/Conflict"); item = self.service.quarantine("A/Alice/p/Studio/Conflict", repair_uuid="repair-2", reason="collision", actor_role="admin", item_count=2)
        self.assertIn("repair_quarantine", self.snapshots)
        self._archive_dir("A/Alice/p/Studio/Restored")
        with self.assertRaises(svc.ServiceConflict): self.service.restore(item["uuid"], "A/Alice/p/Studio/Restored", actor_role="admin")
        self.box.assert_path_exists(self.box.quarantine_root, f"{item['uuid']}/photo.jpg")
        op = self.service.restore(item["uuid"], "A/Alice/p/Studio/Recovered", actor_role="admin")
        self.box.assert_path_exists(self.box.archive_root, "A/Alice/p/Studio/Recovered/photo.jpg")
        self.box.assert_operation(op["uuid"], status=svc.OP_STATUS_SUCCEEDED, related_operation_uuid=item["operation_uuid"])
        self.assertIn("repair_restore", self.snapshots)
