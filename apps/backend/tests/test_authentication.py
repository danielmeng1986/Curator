"""Focused tests for approved-device authentication and authorization."""

from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import repositories as repo
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


if __name__ == "__main__":
    unittest.main()
