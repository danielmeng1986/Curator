"""BT-023 durable cross-workflow traceability acceptance scenarios."""
from __future__ import annotations
import unittest
import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox

class TestCrossWorkflowTraceabilityAcceptance(unittest.TestCase):
    def test_bt023_failed_import_repair_snapshot_and_authentication_remain_linked(self):
        with WorkflowSandbox() as box:
            factory = box.db_factory(); operations = svc.OperationService(repo.OperationRepository(factory))
            issues = svc.IssueService(repo.IssueRepository(factory)); repairs = svc.RepairService(repo.RepairRepository(factory), repo.IssueRepository(factory))
            original = operations.begin("import", svc.OP_INITIATOR_CLI, entity_uuid="album-1", import_uuid="import-1")
            operations.mark_needs_repair(original["uuid"], "filesystem", "filesystem.write-failed", summary="Move failed", repair_state=svc.REPAIR_STATE_NEEDS_REPAIR, recovery_context="Repair canonical path.")
            detected = repairs.detect(original["uuid"], "album-1", "A/Alice/p/Studio/Album", failure_reason="Move failed")
            repair_op = operations.begin("repair", svc.OP_INITIATOR_SYSTEM, repair_uuid=detected["repair"]["uuid"], related_operation_uuid=original["uuid"], issue_uuid=detected["issue"]["uuid"])
            operations.succeed(repair_op["uuid"], "Repair verified.")
            snapshot = operations.begin("snapshot", svc.OP_INITIATOR_SYSTEM, entity_uuid="album-1", summary="Pre-repair snapshot")
            operations.succeed(snapshot["uuid"], "Snapshot created.")
            box.assert_operation(original["uuid"], status=svc.OP_STATUS_NEEDS_REPAIR, import_uuid="import-1", error_category="filesystem", error_code="filesystem.write-failed")
            box.assert_operation(repair_op["uuid"], status=svc.OP_STATUS_SUCCEEDED, repair_uuid=detected["repair"]["uuid"], related_operation_uuid=original["uuid"], issue_uuid=detected["issue"]["uuid"])
            box.assert_operation(snapshot["uuid"], status=svc.OP_STATUS_SUCCEEDED, entity_uuid="album-1")
            box.assert_issue(detected["issue"]["uuid"], affected_operation=original["uuid"], state="Open")

            auth = svc.AuthenticationService(repo.AuthRepository(factory), registration_secret="proof", issue_service=issues, operation_service=operations)
            registration = auth.request_registration(device_name="AI Worker", device_identity="worker-1", requested_role="writer", requested_scopes=["read", "write"], registration_proof="proof")
            issued = auth.approve_registration(registration["uuid"])
            auth.revoke_token(issued["token_record"]["uuid"])
            conn = box.connect()
            try:
                rows = conn.execute("SELECT operation_type, entity_uuid, status FROM operation WHERE operation_type LIKE 'device_%' ORDER BY id").fetchall()
            finally: conn.close()
            self.assertEqual(["device_registration", "device_token_issuance", "device_token_revocation"], [row["operation_type"] for row in rows])
            self.assertTrue(all(row["status"] == svc.OP_STATUS_SUCCEEDED for row in rows))
            self.assertEqual(registration["uuid"], rows[0]["entity_uuid"])
