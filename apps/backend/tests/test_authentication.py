"""Focused tests for approved-device authentication and authorization."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import repositories as repo
import server as srv
import services as svc


class AuthenticationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self.db),
            registration_secret="enrol-me",
            now_fn=lambda: self.now,
        )

    def tearDown(self):
        self.db.close()

    def _request(self, role="writer", scopes=None):
        return self.auth.request_registration(
            device_name="AI Worker",
            device_identity="ai-worker-001",
            requested_role=role,
            requested_scopes=scopes,
            registration_proof="enrol-me",
        )

    def test_unapproved_device_cannot_receive_a_token(self):
        registration = self._request()
        with self.assertRaises(svc.AuthenticationFailure) as context:
            self.auth.authenticate("not-issued")
        self.assertEqual(context.exception.code, "AUTHENTICATION_INVALID_TOKEN")
        self.assertEqual(registration["status"], "PendingApproval")

    def test_approved_trusted_device_receives_and_uses_token(self):
        registration = self._request()
        issued = self.auth.approve_registration(registration["uuid"])
        principal = self.auth.authenticate(issued["token"], "write")
        self.assertEqual(principal["device_name"], "AI Worker")
        self.assertNotIn("token_hash", issued["token_record"])
        persisted = self.db.execute("SELECT token_hash FROM auth_token").fetchone()[0]
        self.assertNotEqual(persisted, issued["token"])
        self.assertEqual(principal["device_identity"], "ai-worker-001")
        self.assertEqual(principal["token_uuid"], issued["token_record"]["uuid"])
        self.assertEqual(principal["expires_at"], issued["token_record"]["expires_at"])
        self.assertIsNone(principal["renewal"])

    def test_expired_token_is_rejected(self):
        registration = self._request()
        issued = self.auth.approve_registration(registration["uuid"], validity=timedelta(seconds=1))
        self.now += timedelta(seconds=2)
        with self.assertRaises(svc.AuthenticationFailure) as context:
            self.auth.authenticate(issued["token"], "read")
        self.assertEqual(context.exception.code, "AUTHENTICATION_EXPIRED_TOKEN")

    def test_revoked_token_is_rejected(self):
        registration = self._request()
        issued = self.auth.approve_registration(registration["uuid"])
        self.auth.revoke_token(issued["token_record"]["uuid"])
        with self.assertRaises(svc.AuthenticationFailure) as context:
            self.auth.authenticate(issued["token"], "read")
        self.assertEqual(context.exception.code, "AUTHENTICATION_REVOKED_TOKEN")

    def test_scope_limited_token_cannot_write(self):
        registration = self._request(role="reader")
        issued = self.auth.approve_registration(registration["uuid"])
        with self.assertRaises(svc.AuthorizationFailure) as context:
            self.auth.authenticate(issued["token"], "write")
        self.assertEqual(context.exception.code, "AUTHORIZATION_INSUFFICIENT_SCOPE")

    def test_approved_renewal_replaces_and_revokes_previous_token(self):
        registration = self._request()
        initial = self.auth.approve_registration(registration["uuid"])
        renewal = self.auth.request_renewal(initial["token"], device_identity="ai-worker-001")
        replacement = self.auth.approve_renewal(renewal["uuid"])
        with self.assertRaises(svc.AuthenticationFailure) as context:
            self.auth.authenticate(initial["token"], "read")
        self.assertEqual(context.exception.code, "AUTHENTICATION_REVOKED_TOKEN")
        self.assertEqual(
            self.auth.authenticate(replacement["token"], "write")["device_name"], "AI Worker"
        )

    def test_duplicate_pending_renewal_is_rejected_and_visible_in_principal(self):
        issued = self.auth.approve_registration(self._request()["uuid"])
        renewal = self.auth.request_renewal(issued["token"], device_identity="ai-worker-001")
        principal = self.auth.authenticate(issued["token"], "read")
        self.assertEqual(principal["renewal"]["uuid"], renewal["uuid"])
        with self.assertRaisesRegex(svc.ServiceConflict, "already pending"):
            self.auth.request_renewal(issued["token"], device_identity="ai-worker-001")

    def test_managed_proof_and_client_owned_token_enrollment(self):
        issued_proof = self.auth.generate_registration_proof()
        candidate = "client-owned-token"
        enrollment_proof = "enrollment-proof-with-more-than-32-characters"
        registration = self.auth.request_registration(
            device_name="Chrome Writer", device_identity="chrome-writer",
            requested_role="writer", requested_scopes=["read", "write"],
            registration_proof=issued_proof["registration_proof"],
            candidate_token_hash=self.auth._hash_token(candidate),
            enrollment_proof=enrollment_proof,
        )
        with self.assertRaises(svc.AuthenticationFailure):
            self.auth.authenticate(candidate)
        approved = self.auth.approve_registration(registration["uuid"])
        self.assertTrue(approved["client_owned"])
        self.assertNotIn("token", approved)
        self.assertEqual("writer", self.auth.authenticate(candidate, "write")["role"])
        status = self.auth.enrollment_status(registration["uuid"], enrollment_proof)
        self.assertEqual("Approved", status["status"])
        with self.assertRaises(svc.AuthenticationFailure):
            self.auth.enrollment_status(registration["uuid"], "wrong-proof")

    def test_rotating_or_disabling_managed_proof_does_not_revoke_tokens(self):
        initial = self.auth.generate_registration_proof()["registration_proof"]
        registration = self.auth.request_registration(
            device_name="Reader", device_identity="managed-reader", requested_role="reader",
            requested_scopes=["read"], registration_proof=initial,
        )
        token = self.auth.approve_registration(registration["uuid"])["token"]
        replacement = self.auth.generate_registration_proof()["registration_proof"]
        with self.assertRaises(svc.AuthenticationFailure):
            self.auth.request_registration(
                device_name="Old proof", device_identity="old-proof", requested_role="reader",
                requested_scopes=["read"], registration_proof=initial,
            )
        self.auth.disable_registration_proof()
        with self.assertRaises(svc.AuthenticationFailure):
            self.auth.request_registration(
                device_name="Disabled", device_identity="disabled-proof", requested_role="reader",
                requested_scopes=["read"], registration_proof=replacement,
            )
        self.assertEqual("reader", self.auth.authenticate(token)["role"])


class BackendNetworkStartupTests(unittest.TestCase):
    def test_lan_address_discovery_keeps_only_private_non_loopback_ipv4(self):
        self.assertEqual(
            ["10.0.0.4", "192.168.1.25"],
            srv.discover_lan_ipv4_addresses([
                "127.0.0.1", "192.168.1.25", "10.0.0.4", "169.254.2.3",
                "8.8.8.8", "0.0.0.0", "not-an-address", "192.168.1.25",
            ]),
        )


class AdministratorBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self.db),
            now_fn=lambda: self.now,
            operation_service=svc.OperationService(repo.OperationRepository(lambda: self.db)),
        )

    def tearDown(self):
        self.db.close()

    def test_first_admin_is_atomic_audited_and_token_is_not_persisted_plaintext(self):
        issued = self.auth.bootstrap_first_admin(
            device_name="Local Administrator",
            device_identity="local-browser-admin",
        )
        principal = self.auth.authenticate(issued["token"], "admin")
        self.assertEqual(principal["role"], "admin")
        self.assertEqual(principal["scopes"], ["admin", "read", "write"])
        self.assertNotIn("token_hash", issued["token_record"])
        stored = self.db.execute("SELECT token_hash FROM auth_token").fetchone()[0]
        self.assertNotEqual(stored, issued["token"])
        operation = self.db.execute(
            "SELECT status, operation_type, summary FROM operation WHERE operation_type = 'administrator_bootstrap'"
        ).fetchone()
        self.assertEqual(operation["status"], "Succeeded")
        self.assertNotIn(issued["token"], operation["summary"])

    def test_second_bootstrap_is_rejected_without_side_effect(self):
        self.auth.bootstrap_first_admin(device_name="Admin", device_identity="admin-1")
        before = tuple(self.db.execute(
            "SELECT (SELECT COUNT(*) FROM device_registration), (SELECT COUNT(*) FROM auth_token), (SELECT COUNT(*) FROM operation)"
        ).fetchone())
        with self.assertRaisesRegex(svc.ServiceConflict, "bootstrap is closed"):
            self.auth.bootstrap_first_admin(device_name="Other", device_identity="admin-2")
        after = tuple(self.db.execute(
            "SELECT (SELECT COUNT(*) FROM device_registration), (SELECT COUNT(*) FROM auth_token), (SELECT COUNT(*) FROM operation)"
        ).fetchone())
        self.assertEqual(after, before)

    def test_expired_or_revoked_admin_does_not_reopen_first_bootstrap(self):
        issued = self.auth.bootstrap_first_admin(device_name="Admin", device_identity="admin-1")
        # Construct historical revoked state below the BT-040 public safety
        # boundary; normal service callers may no longer revoke the last Admin.
        repo.AuthRepository(lambda: self.db).revoke_token(issued["token_record"]["uuid"])
        self.now += timedelta(days=730)
        with self.assertRaisesRegex(svc.ServiceConflict, "already been established"):
            self.auth.bootstrap_first_admin(device_name="Replacement", device_identity="admin-2")

    def test_console_code_is_hashed_short_lived_and_single_use(self):
        created = self.auth.create_bootstrap_code()
        stored = self.db.execute("SELECT code_hash FROM admin_bootstrap_code").fetchone()[0]
        self.assertNotEqual(created["code"], stored)
        issued = self.auth.complete_bootstrap_with_code(
            code=created["code"], device_name="Browser Admin", device_identity="browser-admin",
        )
        self.assertEqual(self.auth.authenticate(issued["token"], "admin")["role"], "admin")
        self.assertIsNotNone(self.db.execute("SELECT used_at FROM admin_bootstrap_code").fetchone()[0])
        with self.assertRaisesRegex(svc.ServiceConflict, "closed"):
            self.auth.complete_bootstrap_with_code(
                code=created["code"], device_name="Replay", device_identity="replay-admin",
            )

    def test_five_wrong_code_attempts_lock_without_creating_authentication_state(self):
        created = self.auth.create_bootstrap_code()
        for attempt in range(5):
            with self.assertRaises(svc.AuthenticationFailure) as context:
                self.auth.complete_bootstrap_with_code(
                    code=f"wrong-{attempt}", device_name="Admin", device_identity="admin",
                )
        self.assertEqual(context.exception.code, "AUTHENTICATION_BOOTSTRAP_CODE_LOCKED")
        with self.assertRaisesRegex(svc.AuthenticationFailure, "locked"):
            self.auth.complete_bootstrap_with_code(
                code=created["code"], device_name="Admin", device_identity="admin",
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM device_registration").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM auth_token").fetchone()[0], 0)
        summaries = " ".join(row[0] for row in self.db.execute(
            "SELECT summary FROM operation WHERE operation_type = 'administrator_bootstrap_rejected'"
        ))
        self.assertNotIn(created["code"], summaries)

    def test_expired_code_is_rejected_without_authentication_state(self):
        created = self.auth.create_bootstrap_code(validity=timedelta(seconds=1))
        self.now += timedelta(seconds=2)
        with self.assertRaisesRegex(svc.AuthenticationFailure, "expired"):
            self.auth.complete_bootstrap_with_code(
                code=created["code"], device_name="Admin", device_identity="admin",
            )
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM auth_token").fetchone()[0], 0)

    def test_audit_failure_compensates_bootstrap_credential(self):
        class FailingOperations:
            def begin(self, *args, **kwargs):
                raise RuntimeError("audit unavailable")

        auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self.db), now_fn=lambda: self.now,
            operation_service=FailingOperations(),
        )
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            auth.bootstrap_first_admin(device_name="Admin", device_identity="admin-fail")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM device_registration").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM auth_token").fetchone()[0], 0)

    def test_cli_prints_token_once_and_refuses_repeat(self):
        with tempfile.TemporaryDirectory(prefix="curator-bootstrap-cli-") as root:
            database = Path(root) / "bootstrap.db"
            command = [
                sys.executable, "-m", "apps.backend", "auth", "bootstrap-admin",
                "--device-name", "CLI Admin", "--device-identity", "cli-admin",
                "--database", str(database),
            ]
            repo_root = Path(__file__).resolve().parents[3]
            first = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            lines = first.stdout.splitlines()
            token = lines[lines.index("Admin Token (shown once):") + 1]
            self.assertTrue(token)
            connection = sqlite3.connect(database)
            try:
                stored = connection.execute("SELECT token_hash FROM auth_token").fetchone()[0]
                logs = " ".join(
                    str(value)
                    for row in connection.execute("SELECT * FROM operation")
                    for value in row if value
                )
            finally:
                connection.close()
            self.assertNotEqual(stored, token)
            self.assertNotIn(token, logs)
            second = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, check=False)
            self.assertEqual(second.returncode, 2)
            self.assertNotIn(token, second.stdout + second.stderr)


if __name__ == "__main__":
    unittest.main()
