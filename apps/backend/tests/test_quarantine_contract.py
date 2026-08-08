"""BT-039 signed Quarantine preview/execution workflow contract."""
import unittest
from pathlib import Path

import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox


class QuarantineContractTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = WorkflowSandbox()
        self.repairs = repo.RepairRepository(self.sandbox.connect)
        self.items = repo.QuarantineRepository(self.sandbox.connect)
        self.operations = svc.OperationService(repo.OperationRepository(self.sandbox.connect))
        quarantine = svc.QuarantineService(
            self.items, self.operations, self.sandbox.archive_root,
            self.sandbox.quarantine_root, lambda reason: self.sandbox.path_under(self.sandbox.snapshot_root, f"{reason}.db"),
        )
        self.contract = svc.QuarantineContractService(
            self.items, self.repairs, quarantine, self.sandbox.archive_root,
            self.sandbox.quarantine_root, b"bt039-test-secret",
        )

    def tearDown(self): self.sandbox.close()

    def _candidate(self):
        relative = "F/Fixture Model/Fixture Studio/Fixture Album"
        source = self.sandbox.path_under(self.sandbox.archive_root, relative)
        source.mkdir(parents=True); (source / "cover.jpg").write_bytes(b"fixture")
        repair = self.repairs.create({"operation_uuid": "origin-op", "expected_path": relative,
                                      "category": "ManualConflict", "failure_reason": "conflict"})
        return repair, relative, source

    def test_quarantine_and_restore_are_preview_bound_single_use_and_intact(self):
        repair, relative, source = self._candidate()
        preview = self.contract.preview_quarantine(repair["uuid"], "isolate conflict")
        self.assertTrue(source.exists(), "preview must not move the source")
        result = self.contract.execute(preview["preview_token"], "admin")
        item = result["item"]
        self.assertFalse(source.exists())
        quarantined = self.sandbox.path_under(self.sandbox.quarantine_root, item["quarantine_path"])
        self.assertTrue((quarantined / "cover.jpg").exists())
        with self.assertRaises(svc.ServiceConflict) as replay:
            self.contract.execute(preview["preview_token"], "admin")
        self.assertEqual("QUARANTINE_PREVIEW_REPLAYED", replay.exception.code)

        restore = self.contract.preview_restore(item["uuid"])
        restored = self.contract.execute(restore["preview_token"], "admin")
        self.assertTrue((source / "cover.jpg").exists())
        self.assertIsNotNone(restored["item"]["restored_at"])
        self.assertTrue(restored["operation_uuid"])

    def test_changed_directory_rejects_preview_without_move_or_claim(self):
        repair, _relative, source = self._candidate()
        preview = self.contract.preview_quarantine(repair["uuid"], "isolate conflict")
        (source / "new.jpg").write_bytes(b"changed")
        with self.assertRaises(svc.ServiceConflict) as stale:
            self.contract.execute(preview["preview_token"], "admin")
        self.assertEqual("QUARANTINE_PREVIEW_STALE", stale.exception.code)
        self.assertTrue(source.exists())
        self.assertFalse(self.items.preview_is_claimed(preview["preview_uuid"]))

    def test_restore_collision_is_rejected_before_preview(self):
        repair, _relative, source = self._candidate()
        item = self.contract.execute(
            self.contract.preview_quarantine(repair["uuid"], "isolate conflict")["preview_token"], "admin",
        )["item"]
        source.mkdir(parents=True); (source / "other.jpg").write_bytes(b"other")
        with self.assertRaises(svc.ServiceConflict) as collision:
            self.contract.preview_restore(item["uuid"])
        self.assertEqual("RESTORE_DESTINATION_EXISTS", collision.exception.code)


if __name__ == "__main__": unittest.main()
