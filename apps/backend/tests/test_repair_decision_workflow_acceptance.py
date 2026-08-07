"""BT-022 end-to-end repair decision safety scenarios."""
from __future__ import annotations
import unittest
import repositories as repo
import services as svc
from workflow_support import WorkflowSandbox

class TestRepairDecisionWorkflowAcceptance(unittest.TestCase):
    def test_bt022_assisted_confirmation_and_failed_verification_remain_unresolved(self):
        with WorkflowSandbox() as box:
            factory = box.db_factory(); repair = svc.RepairService(repo.RepairRepository(factory), repo.IssueRepository(factory))
            outcome = repair.detect("failed-op", "album-1", "A/Alice/p/Studio/Album", category=svc.REPAIR_CATEGORY_ASSISTED, failure_reason="near match needs confirmation")
            repair_uuid = outcome["repair"]["uuid"]
            with self.assertRaises(svc.ServiceConflict): repair.start_repair(repair_uuid)
            repair.confirm(repair_uuid, "I confirm the displayed source and destination.")
            repair.start_repair(repair_uuid); repair.complete_action(repair_uuid)
            repair.verify(repair_uuid, passed=False, result="canonical path still mismatches")
            box.assert_repair_case(repair_uuid, state=svc.REPAIR_STATE_NEEDS_REPAIR, verification_result="canonical path still mismatches")
            box.assert_issue(outcome["issue"]["uuid"], state="Open")
