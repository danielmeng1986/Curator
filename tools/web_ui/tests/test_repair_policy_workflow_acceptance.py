"""BT-028 repair-decision policy workflow acceptance scenarios."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox


class TestRepairDecisionPolicyWorkflowAcceptance(unittest.TestCase):
    """Exercise policy outcomes through durable records and sandbox files."""

    def setUp(self):
        self.sandbox = WorkflowSandbox()
        factory = self.sandbox.db_factory()
        self.repair = svc.RepairService(repo.RepairRepository(factory), repo.IssueRepository(factory))
        self.operations = svc.OperationService(repo.OperationRepository(factory))
        self.audit = []
        self.policy = svc.RepairDecisionService(
            self.repair, self.operations, repo.RepairSuppressionRepository(factory),
            self.sandbox.archive_root, self.audit.append,
        )

    def tearDown(self):
        self.sandbox.close()

    def _create_archive_directory(self, relative_path, files=()):
        directory = self.sandbox.path_under(self.sandbox.archive_root, relative_path)
        directory.mkdir(parents=True, exist_ok=False)
        for filename in files:
            (directory / filename).touch()
        return directory

    def test_bt028_only_canonicalization_only_rename_is_automatic(self):
        self._create_archive_directory("A/ Alice /p/Studio/Album", files=("photo.jpg",))
        detected = self.repair.detect("failed-import", "album-1", "A/Alice/p/Studio/Album", category=svc.REPAIR_CATEGORY_AUTOMATIC)
        repair_uuid = detected["repair"]["uuid"]

        decision = self.policy.classify(["A/ Alice /p/Studio/Album"], "A/Alice/p/Studio/Album")
        self.assertEqual(svc.REPAIR_CATEGORY_AUTOMATIC, decision["category"])
        operation = self.policy.execute_automatic_rename(repair_uuid, "A/ Alice /p/Studio/Album", "A/Alice/p/Studio/Album")

        self.sandbox.assert_path_missing(self.sandbox.archive_root, "A/ Alice /p/Studio/Album")
        self.sandbox.assert_path_exists(self.sandbox.archive_root, "A/Alice/p/Studio/Album/photo.jpg")
        self.sandbox.assert_operation(operation["uuid"], status=svc.OP_STATUS_SUCCEEDED, repair_uuid=repair_uuid)
        self.sandbox.assert_repair_case(repair_uuid, state=svc.REPAIR_STATE_PENDING_VERIFICATION)
        self.assertEqual("repair_automatic_rename", self.audit[-1]["action"])
        self.repair.verify(repair_uuid, passed=True, result="path checks passed")
        self.sandbox.assert_repair_case(repair_uuid, state=svc.REPAIR_STATE_RESOLVED)

    def test_bt028_ineligible_or_ambiguous_paths_cannot_be_silently_repaired(self):
        self._create_archive_directory("A/Alice  Smith/p/Studio/Album")
        assisted = self.policy.classify(
            ["A/Alice  Smith/p/Studio/Album"], "A/Alice Smith/p/Studio/Album",
            authoritative_path="A/Alice  Smith/p/Studio/Album",
        )
        self.assertEqual(svc.REPAIR_CATEGORY_ASSISTED, assisted["category"])

        self._create_archive_directory("B/Bob/p/Studio/Album")
        self._create_archive_directory("C/Bob/p/Studio/Album")
        manual = self.policy.classify(
            ["B/Bob/p/Studio/Album", "C/Bob/p/Studio/Album"], "B/Bob/p/Studio/Final",
        )
        self.assertEqual(svc.REPAIR_CATEGORY_MANUAL_CONFLICT, manual["category"])

        detected = self.repair.detect("op-2", "album-2", "A/Alice Smith/p/Studio/Album", category=svc.REPAIR_CATEGORY_ASSISTED)
        with self.assertRaises(svc.ServiceConflict) as error:
            self.policy.execute_automatic_rename(detected["repair"]["uuid"], "A/Alice  Smith/p/Studio/Album", "A/Alice Smith/p/Studio/Album")
        self.assertEqual("AUTOMATIC_POLICY_REJECTED", error.exception.code)
        self.sandbox.assert_path_exists(self.sandbox.archive_root, "A/Alice  Smith/p/Studio/Album")

    def test_bt028_ignored_rediscovery_and_bounded_admin_suppression(self):
        first = self.repair.detect("op-3", "album-3", "A/Alice/p/Studio/Album")
        self.repair.ignore(first["repair"]["uuid"])
        rediscovered = self.repair.detect("op-3", "album-3", "A/Alice/p/Studio/Album")
        self.assertNotEqual(first["repair"]["uuid"], rediscovered["repair"]["uuid"])
        self.sandbox.assert_repair_case(first["repair"]["uuid"], state=svc.REPAIR_STATE_IGNORED)

        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        with self.assertRaises(svc.ServiceConflict):
            self.policy.create_suppression(fingerprint="fp-1", scope_path="A/Alice", reason="accepted exception", creator="writer", actor_role="writer", expires_at=expiry)
        record = self.policy.create_suppression(fingerprint="fp-1", scope_path="A/Alice", reason="accepted exception", creator="admin", actor_role="admin", expires_at=expiry)
        self.assertTrue(self.policy.is_suppressed("fp-1", "A/Alice"))
        self.assertFalse(self.policy.is_suppressed("fp-1", "A/Alice", now=datetime.now(timezone.utc) + timedelta(days=1)))
        self.policy.revoke_suppression(record["uuid"], actor="admin", actor_role="admin")
        self.assertFalse(self.policy.is_suppressed("fp-1", "A/Alice"))
        self.assertIn("repair_suppression_applied", [entry["action"] for entry in self.audit])
