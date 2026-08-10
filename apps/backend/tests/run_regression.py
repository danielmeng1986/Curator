#!/usr/bin/env python3
"""Run Curator Backend regression tests by specification boundary.

The runner deliberately loads the existing isolated unittest suites instead of
introducing a second test framework.  ``all`` is discovery-based so it remains
the complete Backend regression suite; named groups provide focused failures
for the controlling specification boundary.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TEST_DIR.parent
REPO_ROOT = BACKEND_DIR.parents[1]

GROUPS: dict[str, tuple[str, ...]] = {
    "api": (
        "test_api_contract",
    ),
    "api-workflow": (
        "test_api_contract.TestAuthenticatedApiWorkflow",
        "test_api_contract.TestOperationHistoryDisclosure",
    ),
    "repository": (
        "test_repositories",
        "test_canonical_path",
    ),
    "workspace": (
        "test_repositories.TestWorkspaceAlbumRepositoryCreate",
        "test_repositories.TestWorkspaceAlbumRepositoryLifecyclePersistence",
        "test_services.TestWorkspaceAlbumServiceCreate",
        "test_services.TestWorkspaceAlbumServiceLifecycleTransitions",
        "test_services.TestWorkspaceAlbumServiceUpdate",
        "test_services.TestWorkspaceAlbumServiceBatchUpdate",
    ),
    "authentication": (
        "test_authentication",
        "test_api_contract.TestVersionedApiAuthorization",
    ),
    "snapshots": (
        "test_services.TestBackupServiceCreate",
        "test_services.TestBackupServiceRollback",
        "test_services.TestAssessOperationRisk",
        "test_services.TestIsRetentionEligible",
        "test_services.TestBackupServicePurgeEligible",
        "test_services.TestBackupServiceRestoreSuccess",
    ),
    "operations": (
        "test_repositories.TestOperationRepositoryCreate",
        "test_repositories.TestOperationRepositorySetStatus",
        "test_services.TestOperationServiceBegin",
        "test_services.TestOperationServiceSucceed",
        "test_services.TestOperationServiceFail",
        "test_services.TestOperationServiceNeedsRepair",
        "test_services.TestOperationServiceCancel",
        "test_services.TestOperationServiceWorkflowIntegration",
    ),
    "workflow": (
        "test_workflow_foundation",
        "test_import_workflow_acceptance",
        "test_workspace_workflow_acceptance",
        "test_repair_policy_workflow_acceptance",
        "test_quarantine_workflow_acceptance",
        "test_repair_decision_workflow_acceptance",
        "test_traceability_workflow_acceptance",
        "test_ai_workspace_workflow_acceptance",
    ),
    "workflow-readiness": (
        "test_workflow_foundation",
        "test_import_workflow_acceptance",
        "test_workspace_workflow_acceptance",
        "test_repair_policy_workflow_acceptance",
        "test_quarantine_workflow_acceptance",
        "test_repair_decision_workflow_acceptance",
        "test_traceability_workflow_acceptance",
        "test_ai_workspace_workflow_acceptance",
        "test_api_contract.TestAuthenticatedApiWorkflow",
        "test_api_contract.TestOperationHistoryDisclosure",
    ),
    "ai-workspace-workflow": (
        "test_ai_workspace_workflow_acceptance",
    ),
}


def build_suite(group: str) -> unittest.TestSuite:
    """Load one named specification group or the complete regression suite."""
    loader = unittest.defaultTestLoader
    if group == "all":
        return loader.discover(str(TEST_DIR), pattern="test_*.py")
    return unittest.TestSuite(loader.loadTestsFromName(name) for name in GROUPS[group])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "group",
        choices=("all", *GROUPS),
        nargs="?",
        default="all",
        help="specification-aligned group to run (default: all)",
    )
    args = parser.parse_args(argv)

    # Existing focused tests load sibling modules by filename. Keep that
    # compatibility while the authoritative package remains apps.backend.
    sys.path.insert(0, str(REPO_ROOT))
    sys.path.insert(0, str(BACKEND_DIR))
    sys.path.insert(0, str(TEST_DIR))
    result = unittest.TextTestRunner(verbosity=2).run(build_suite(args.group))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
