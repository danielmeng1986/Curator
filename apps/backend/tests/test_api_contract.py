#!/usr/bin/env python3
"""Focused API contract tests.

Covers:
- Success response envelope shape (data + meta + request_id)
- Validation / request failure response envelope (error + meta)
- Server error response envelope (INTERNAL_ERROR, no implementation details)
- Collection response envelope (data array + pagination + filters + sort)
- Cursor encode/decode round-trip and invalid-cursor safety
- HTTP handler integration: envelopes produced by AppHandler for each
  outcome class, using an in-memory SQLite database and a real HTTP server
  started on a free port.
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import threading
import unittest
from datetime import timedelta
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch

# Make the tools/web_ui package importable.
sys.path.insert(0, str(Path(__file__).parent.parent))

import api_contract


# ---------------------------------------------------------------------------
# Unit tests for api_contract module
# ---------------------------------------------------------------------------

class TestSuccessEnvelope(unittest.TestCase):
    """api_contract.success_response produces the required envelope shape."""

    def _make(self, data, **kwargs):
        return api_contract.success_response(data, request_id="req-test", **kwargs)

    def test_has_data_and_meta_keys(self):
        resp = self._make({"id": 1})
        self.assertIn("data", resp)
        self.assertIn("meta", resp)

    def test_does_not_have_ok_or_error_keys(self):
        resp = self._make({"id": 1})
        self.assertNotIn("ok", resp)
        self.assertNotIn("error", resp)

    def test_meta_contains_request_id(self):
        resp = api_contract.success_response({}, request_id="req-abc-123")
        self.assertEqual(resp["meta"]["request_id"], "req-abc-123")

    def test_data_preserves_object(self):
        data = {"id": 42, "name": "Northlight"}
        resp = self._make(data)
        self.assertEqual(resp["data"], data)

    def test_data_can_be_list(self):
        items = [{"id": 1}, {"id": 2}]
        resp = self._make(items)
        self.assertEqual(resp["data"], items)

    def test_data_can_be_null(self):
        resp = self._make(None)
        self.assertIsNone(resp["data"])

    def test_meta_extras_are_merged_into_meta(self):
        extras = {"operation": {"id": "op-01"}}
        resp = self._make({}, meta_extras=extras)
        self.assertEqual(resp["meta"]["operation"], {"id": "op-01"})
        self.assertIn("request_id", resp["meta"])

    def test_meta_extras_none_does_not_add_extra_keys(self):
        resp = self._make({}, meta_extras=None)
        self.assertEqual(set(resp["meta"].keys()), {"request_id"})


class TestErrorEnvelope(unittest.TestCase):
    """api_contract.error_response produces the required envelope shape."""

    def _make(self, code="NOT_FOUND", message="Not found.", **kwargs):
        return api_contract.error_response(code, message, request_id="req-err", **kwargs)

    def test_has_error_and_meta_keys(self):
        resp = self._make()
        self.assertIn("error", resp)
        self.assertIn("meta", resp)

    def test_does_not_have_ok_or_data_keys(self):
        resp = self._make()
        self.assertNotIn("ok", resp)
        self.assertNotIn("data", resp)

    def test_error_contains_code_and_message(self):
        resp = self._make("INTERNAL_ERROR", "An error occurred.")
        self.assertEqual(resp["error"]["code"], "INTERNAL_ERROR")
        self.assertEqual(resp["error"]["message"], "An error occurred.")

    def test_meta_contains_request_id(self):
        resp = api_contract.error_response("NOT_FOUND", ".", request_id="req-xyz")
        self.assertEqual(resp["meta"]["request_id"], "req-xyz")

    def test_optional_details_omitted_when_absent(self):
        resp = self._make()
        self.assertNotIn("details", resp["error"])

    def test_optional_fields_omitted_when_absent(self):
        resp = self._make()
        self.assertNotIn("fields", resp["error"])

    def test_details_included_when_provided(self):
        resp = self._make(details={"resource_id": "album-01"})
        self.assertEqual(resp["error"]["details"], {"resource_id": "album-01"})

    def test_fields_included_when_provided(self):
        fields = {"name": [{"code": "REQUIRED", "message": "Name is required."}]}
        resp = self._make(fields=fields)
        self.assertEqual(resp["error"]["fields"], fields)

    def test_internal_error_message_does_not_expose_sql_or_traceback(self):
        """A properly-formed INTERNAL_ERROR must not leak implementation details."""
        resp = api_contract.error_response(
            "INTERNAL_ERROR",
            "An unexpected server error occurred.",
            request_id="req-1",
        )
        msg = resp["error"]["message"].lower()
        self.assertNotIn("traceback", msg)
        self.assertNotIn("sqlite3", msg)
        self.assertNotIn("sql", msg)
        self.assertNotIn("exception", msg)

    def test_meta_extras_included_in_meta(self):
        extras = {"confirmation": {"id": "conf-01", "required": True}}
        resp = self._make(meta_extras=extras)
        self.assertEqual(resp["meta"]["confirmation"]["id"], "conf-01")

    def test_validation_error_uses_request_star_code_family_for_400(self):
        resp = api_contract.error_response(
            "REQUEST_MISSING_FIELD", "A required field is absent.", request_id="req-1"
        )
        self.assertTrue(
            resp["error"]["code"].startswith("REQUEST_"),
            "400-class transport errors must use REQUEST_* code family",
        )

    def test_not_found_code(self):
        resp = api_contract.error_response("NOT_FOUND", ".", request_id="req-1")
        self.assertEqual(resp["error"]["code"], "NOT_FOUND")

    def test_business_conflict_code(self):
        resp = api_contract.error_response("BUSINESS_CONFLICT", ".", request_id="req-1")
        self.assertEqual(resp["error"]["code"], "BUSINESS_CONFLICT")


class TestCollectionMeta(unittest.TestCase):
    """api_contract.build_collection_meta produces the required metadata shape."""

    def _make(self, **overrides):
        defaults = dict(
            cursor=None,
            limit=50,
            next_cursor=None,
            has_more=False,
            total=None,
            filters=[],
            sort=[],
        )
        defaults.update(overrides)
        return api_contract.build_collection_meta(**defaults)

    def test_pagination_key_present(self):
        meta = self._make()
        self.assertIn("pagination", meta)

    def test_filters_always_present(self):
        meta = self._make()
        self.assertIn("filters", meta)
        self.assertIsInstance(meta["filters"], list)

    def test_sort_always_present(self):
        meta = self._make()
        self.assertIn("sort", meta)
        self.assertIsInstance(meta["sort"], list)

    def test_pagination_fields(self):
        meta = self._make(
            cursor=None, limit=10, next_cursor="tok-next", has_more=True, total=25
        )
        p = meta["pagination"]
        self.assertIsNone(p["cursor"])
        self.assertEqual(p["limit"], 10)
        self.assertEqual(p["next_cursor"], "tok-next")
        self.assertTrue(p["has_more"])
        self.assertEqual(p["total"], 25)

    def test_first_page_cursor_is_null(self):
        meta = self._make(cursor=None)
        self.assertIsNone(meta["pagination"]["cursor"])

    def test_last_page_next_cursor_is_null(self):
        meta = self._make(next_cursor=None, has_more=False)
        self.assertIsNone(meta["pagination"]["next_cursor"])
        self.assertFalse(meta["pagination"]["has_more"])

    def test_has_more_is_always_bool(self):
        meta = self._make(has_more=True)
        self.assertIsInstance(meta["pagination"]["has_more"], bool)
        meta2 = self._make(has_more=False)
        self.assertIsInstance(meta2["pagination"]["has_more"], bool)

    def test_total_can_be_null(self):
        meta = self._make(total=None)
        self.assertIsNone(meta["pagination"]["total"])

    def test_total_can_be_integer(self):
        meta = self._make(total=42)
        self.assertEqual(meta["pagination"]["total"], 42)

    def test_filters_and_sort_preserved(self):
        filters = [{"field": "status", "operator": "exact", "value": "active"}]
        sort = [{"field": "title", "direction": "asc"}]
        meta = self._make(filters=filters, sort=sort)
        self.assertEqual(meta["filters"], filters)
        self.assertEqual(meta["sort"], sort)

    def test_filters_none_defaults_to_empty_list(self):
        meta = api_contract.build_collection_meta(
            cursor=None, limit=50, next_cursor=None, has_more=False, total=0
        )
        self.assertEqual(meta["filters"], [])
        self.assertEqual(meta["sort"], [])


class TestCursorEncoding(unittest.TestCase):
    """Opaque cursor encoding/decoding."""

    def test_roundtrip_non_zero_offset(self):
        encoded = api_contract.encode_cursor(100)
        decoded = api_contract.decode_cursor(encoded)
        self.assertEqual(decoded, 100)

    def test_roundtrip_zero_offset(self):
        encoded = api_contract.encode_cursor(0)
        decoded = api_contract.decode_cursor(encoded)
        self.assertEqual(decoded, 0)

    def test_different_offsets_produce_different_cursors(self):
        self.assertNotEqual(
            api_contract.encode_cursor(10), api_contract.encode_cursor(20)
        )

    def test_invalid_cursor_returns_none(self):
        self.assertIsNone(api_contract.decode_cursor("not-a-valid-cursor!!"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(api_contract.decode_cursor(""))

    def test_encoded_cursor_is_url_safe_string(self):
        encoded = api_contract.encode_cursor(999)
        self.assertIsInstance(encoded, str)
        # URL-safe base64 uses only A-Z, a-z, 0-9, -, _, and =
        for ch in encoded:
            self.assertIn(ch, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=")

    def test_decoded_value_is_int(self):
        encoded = api_contract.encode_cursor(7)
        decoded = api_contract.decode_cursor(encoded)
        self.assertIsInstance(decoded, int)


class TestGenerateRequestId(unittest.TestCase):
    def test_returns_non_empty_string(self):
        rid = api_contract.generate_request_id()
        self.assertIsInstance(rid, str)
        self.assertTrue(len(rid) > 0)

    def test_each_call_produces_unique_id(self):
        ids = {api_contract.generate_request_id() for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_starts_with_req_prefix(self):
        rid = api_contract.generate_request_id()
        self.assertTrue(rid.startswith("req-"))


# ---------------------------------------------------------------------------
# HTTP integration tests
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    display_name TEXT,
    primary_name TEXT,
    description TEXT,
    country TEXT,
    ethnicity TEXT,
    eye_color TEXT,
    natural_hair_color TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS studio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    name TEXT,
    website TEXT,
    description TEXT,
    media_scope TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    studio_id INTEGER,
    status_id INTEGER,
    title TEXT,
    description TEXT,
    scene TEXT,
    location TEXT,
    capture_date TEXT,
    publish_date TEXT,
    rating REAL,
    path TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS album_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER,
    model_id INTEGER,
    age_when_shot REAL,
    role TEXT,
    remarks TEXT
);
CREATE TABLE IF NOT EXISTS album_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER,
    related_album_id INTEGER,
    relation_type TEXT,
    remarks TEXT
);
CREATE TABLE IF NOT EXISTS photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    album_id INTEGER,
    filename TEXT,
    relative_path TEXT,
    hash TEXT,
    width INTEGER,
    height INTEGER,
    capture_time TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS workspace_album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    status_id INTEGER,
    studio_name TEXT,
    album_name TEXT,
    primary_model TEXT,
    additional_models TEXT,
    remark TEXT,
    current_path TEXT,
    expected_path TEXT,
    ai_result TEXT,
    belongs_to_album_id INTEGER,
    album_id INTEGER
);
"""


def _make_test_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_SQL)
    conn.execute("INSERT INTO status (name, description) VALUES ('Active', 'Active albums')")
    conn.commit()
    return conn


class _TestServerBase(unittest.TestCase):
    """Base class that starts a real HTTP server backed by an in-memory DB."""

    _server: HTTPServer | None = None
    _thread: threading.Thread | None = None
    _db: sqlite3.Connection | None = None
    _port: int = 0

    @classmethod
    def setUpClass(cls):
        import server as srv

        cls._db = _make_test_db()

        def fake_open_db():
            return cls._db

        cls._open_db_patcher = patch.object(srv, "open_db", side_effect=fake_open_db)
        cls._db_exists_patcher = patch.object(
            srv, "DATABASE_PATH", new_callable=lambda: type("_FakePath", (), {
                "exists": lambda self: True,
                "__str__": lambda self: ":memory:",
            })()
        )

        cls._open_db_patcher.start()

        cls._server = HTTPServer(("127.0.0.1", 0), srv.AppHandler)
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls._server:
            cls._server.shutdown()
        cls._open_db_patcher.stop()
        if cls._db:
            cls._db.close()

    def _get(self, path: str, headers: dict | None = None) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET", path, headers=headers or {})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        return resp.status, body

    def _post(self, path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode()
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        conn.request("POST", path, body=data, headers=request_headers)
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        return resp.status, body

    def _delete(self, path: str) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("DELETE", path)
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        return resp.status, body


class TestHttpSuccessEnvelope(_TestServerBase):
    """GET /api/statuses → 200 success envelope."""

    def test_success_response_has_data_and_meta(self):
        status, body = self._get("/api/statuses")
        self.assertEqual(status, 200)
        self.assertIn("data", body)
        self.assertIn("meta", body)
        self.assertNotIn("ok", body)
        self.assertNotIn("error", body)

    def test_success_meta_has_request_id(self):
        _, body = self._get("/api/statuses")
        self.assertIn("request_id", body["meta"])
        self.assertTrue(body["meta"]["request_id"].startswith("req-"))

    def test_success_data_contains_statuses(self):
        _, body = self._get("/api/statuses")
        self.assertIn("statuses", body["data"])

    def test_each_request_gets_unique_request_id(self):
        _, b1 = self._get("/api/statuses")
        _, b2 = self._get("/api/statuses")
        self.assertNotEqual(b1["meta"]["request_id"], b2["meta"]["request_id"])


class TestHttpValidationError(_TestServerBase):
    """POST /api/statuses without name → 400 REQUEST_MISSING_FIELD."""

    def test_validation_error_has_error_and_meta(self):
        status, body = self._post("/api/statuses", {})
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertIn("meta", body)
        self.assertNotIn("ok", body)
        self.assertNotIn("data", body)

    def test_validation_error_code_is_request_family(self):
        _, body = self._post("/api/statuses", {})
        self.assertTrue(
            body["error"]["code"].startswith("REQUEST_"),
            f"Expected REQUEST_* code, got: {body['error']['code']}",
        )

    def test_validation_error_message_is_present(self):
        _, body = self._post("/api/statuses", {})
        self.assertIsInstance(body["error"]["message"], str)
        self.assertTrue(len(body["error"]["message"]) > 0)

    def test_validation_error_meta_has_request_id(self):
        _, body = self._post("/api/statuses", {})
        self.assertIn("request_id", body["meta"])

    def test_invalid_json_body_returns_400(self):
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request(
            "POST",
            "/api/statuses",
            body=b"not valid json{{{",
            headers={"Content-Type": "application/json", "Content-Length": "17"},
        )
        resp = conn.getresponse()
        body = json.loads(resp.read().decode())
        conn.close()
        self.assertEqual(resp.status, 400)
        self.assertEqual(body["error"]["code"], "REQUEST_INVALID_JSON")
        self.assertIn("request_id", body["meta"])


class TestHttpNotFoundError(_TestServerBase):
    """GET /api/models/999999 → 404 NOT_FOUND."""

    def test_not_found_returns_404(self):
        status, body = self._get("/api/models/999999")
        self.assertEqual(status, 404)

    def test_not_found_error_envelope(self):
        _, body = self._get("/api/models/999999")
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")
        self.assertIn("meta", body)
        self.assertNotIn("ok", body)

    def test_unknown_route_returns_404(self):
        status, body = self._get("/api/nonexistent-route")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")


class TestHttpServerError(_TestServerBase):
    """Simulate an unexpected error → 500 INTERNAL_ERROR."""

    def test_internal_error_returns_500_with_envelope(self):
        import server as srv

        def boom():
            raise RuntimeError("sqlite3 internal state: database is locked [SQL: SELECT 1]")

        with patch.object(srv, "build_backup_catalog", side_effect=boom):
            status, body = self._get("/api/health")

        self.assertEqual(status, 500)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "INTERNAL_ERROR")
        self.assertNotIn("ok", body)
        self.assertNotIn("data", body)

    def test_internal_error_does_not_expose_sql(self):
        import server as srv

        def boom():
            raise RuntimeError("sqlite3 error: no such table: album")

        with patch.object(srv, "build_backup_catalog", side_effect=boom):
            _, body = self._get("/api/health")

        # The contract-compliant error message must not include raw exception text
        msg = body["error"]["message"].lower()
        self.assertNotIn("sqlite3", msg)
        self.assertNotIn("no such table", msg)
        self.assertNotIn("album", msg)

    def test_internal_error_meta_has_request_id(self):
        import server as srv

        with patch.object(srv, "build_backup_catalog", side_effect=RuntimeError("fail")):
            _, body = self._get("/api/health")

        self.assertIn("request_id", body["meta"])


class TestHttpCollectionEnvelope(_TestServerBase):
    """GET /api/models → 200 collection with pagination meta."""

    def test_collection_has_data_and_meta(self):
        status, body = self._get("/api/models")
        self.assertEqual(status, 200)
        self.assertIn("data", body)
        self.assertIn("meta", body)

    def test_collection_data_is_list(self):
        _, body = self._get("/api/models")
        self.assertIsInstance(body["data"], list)

    def test_collection_meta_has_pagination(self):
        _, body = self._get("/api/models")
        self.assertIn("pagination", body["meta"])

    def test_collection_pagination_fields_present(self):
        _, body = self._get("/api/models")
        p = body["meta"]["pagination"]
        for key in ("cursor", "limit", "next_cursor", "has_more", "total"):
            self.assertIn(key, p, f"pagination.{key} missing")

    def test_collection_meta_has_filters_and_sort(self):
        _, body = self._get("/api/models")
        self.assertIn("filters", body["meta"])
        self.assertIn("sort", body["meta"])
        self.assertIsInstance(body["meta"]["filters"], list)
        self.assertIsInstance(body["meta"]["sort"], list)

    def test_first_page_cursor_is_null(self):
        _, body = self._get("/api/models")
        self.assertIsNone(body["meta"]["pagination"]["cursor"])

    def test_has_more_is_boolean(self):
        _, body = self._get("/api/models")
        self.assertIsInstance(body["meta"]["pagination"]["has_more"], bool)

    def test_collection_does_not_have_old_total_offset_keys(self):
        _, body = self._get("/api/models")
        self.assertNotIn("total", body)
        self.assertNotIn("offset", body)
        self.assertNotIn("limit", body)
        self.assertNotIn("models", body)

    def test_studios_collection_envelope(self):
        status, body = self._get("/api/studios")
        self.assertEqual(status, 200)
        self.assertIsInstance(body["data"], list)
        self.assertIn("pagination", body["meta"])

    def test_albums_collection_envelope(self):
        status, body = self._get("/api/albums")
        self.assertEqual(status, 200)
        self.assertIsInstance(body["data"], list)
        self.assertIn("pagination", body["meta"])


class TestHttpConflictError(_TestServerBase):
    """DELETE on referenced resource → 409 BUSINESS_CONFLICT."""

    def _insert_album_for_status(self):
        import uuid as _uuid
        self._db.execute(
            "INSERT INTO album (uuid, status_id, title, created_at, updated_at) VALUES (?, 1, 'T', '2024-01-01', '2024-01-01')",
            (_uuid.uuid4().hex,),
        )
        self._db.commit()

    def test_delete_referenced_status_returns_409(self):
        self._insert_album_for_status()
        status, body = self._delete("/api/statuses/1")
        self.assertEqual(status, 409)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "BUSINESS_CONFLICT")
        self.assertNotIn("ok", body)

    def test_conflict_meta_has_request_id(self):
        self._insert_album_for_status()
        _, body = self._delete("/api/statuses/1")
        self.assertIn("request_id", body["meta"])


class TestVersionedApiAuthorization(_TestServerBase):
    """Versioned routes enforce bearer state and scopes before dispatch."""

    def _issue(self, *, role="reader", validity=None):
        import repositories as repo
        import services as svc

        auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self._db), registration_secret="local-proof"
        )
        suffix = str(self._db.execute("SELECT COUNT(*) FROM device_registration").fetchone()[0]) if self._table_exists("device_registration") else "0"
        registration = auth.request_registration(
            device_name="test device",
            device_identity=f"test-device-{suffix}",
            requested_role=role,
            requested_scopes=None,
            registration_proof="local-proof",
        )
        return auth.approve_registration(registration["uuid"], validity=validity)

    def _table_exists(self, name):
        return self._db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone() is not None

    @staticmethod
    def _bearer(issued):
        return {"Authorization": f"Bearer {issued['token']}"}

    def test_versioned_route_rejects_missing_token(self):
        status, body = self._get("/api/v1/statuses")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "AUTHENTICATION_MISSING_TOKEN")

    def test_versioned_route_allows_approved_scoped_token(self):
        issued = self._issue()
        status, body = self._get("/api/v1/statuses", self._bearer(issued))
        self.assertEqual(status, 200)
        self.assertIn("data", body)

    def test_versioned_route_rejects_expired_token(self):
        issued = self._issue(validity=timedelta(microseconds=1))
        status, body = self._get("/api/v1/statuses", self._bearer(issued))
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "AUTHENTICATION_EXPIRED_TOKEN")

    def test_versioned_route_rejects_revoked_token(self):
        issued = self._issue()
        import repositories as repo
        import services as svc
        svc.AuthenticationService(repo.AuthRepository(lambda: self._db)).revoke_token(issued["token_record"]["uuid"])
        status, body = self._get("/api/v1/statuses", self._bearer(issued))
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "AUTHENTICATION_REVOKED_TOKEN")

    def test_reader_token_cannot_perform_write(self):
        issued = self._issue(role="reader")
        status, body = self._post("/api/v1/statuses", {"name": "Blocked"}, self._bearer(issued))
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "AUTHORIZATION_INSUFFICIENT_SCOPE")


class TestAuthenticatedApiWorkflow(_TestServerBase):
    """BT-024: loopback enrolment then protected import entry."""

    def test_invalid_unicode_registration_proof_is_rejected_safely(self):
        import server as srv
        with patch.object(srv, "AUTH_REGISTRATION_SECRET", "test-proof"):
            status, body = self._post("/api/auth/registrations", {
                "device_name": "workflow worker", "device_identity": "invalid-proof-worker",
                "requested_role": "writer", "requested_scopes": ["read", "write"],
                "registration_proof": "不是 test-proof",
            })
        self.assertEqual(401, status)
        self.assertEqual("AUTHENTICATION_INVALID_REGISTRATION_PROOF", body["error"]["code"])

    def test_registration_approval_and_writer_import_preview(self):
        import server as srv
        with patch.object(srv, "AUTH_REGISTRATION_SECRET", "test-proof"):
            status, body = self._post("/api/auth/registrations", {
                "device_name": "workflow worker", "device_identity": "workflow-worker-1",
                "requested_role": "writer", "requested_scopes": ["read", "write"],
                "registration_proof": "test-proof",
            })
            self.assertEqual(201, status)
            registration = body["data"]["registration"]
            self.assertEqual("PendingApproval", registration["status"])
            status, issued_body = self._post(f"/api/auth/registrations/{registration['uuid']}/approve", {})
        self.assertEqual(200, status)
        issued = issued_body["data"]
        self.assertIn("token", issued)
        self.assertNotIn("token_hash", issued["token_record"])
        headers = {"Authorization": f"Bearer {issued['token']}"}
        status, preview = self._post("/api/v1/import/preview", {"items": []}, headers)
        self.assertEqual(200, status)
        self.assertIn("preview", preview["data"])

    def test_rejected_import_request_has_no_business_side_effect(self):
        before = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        status, body = self._post("/api/v1/import/preview", {"items": []})
        self.assertEqual(401, status)
        self.assertEqual("AUTHENTICATION_MISSING_TOKEN", body["error"]["code"])
        after = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        self.assertEqual(before, after)


class TestOperationHistoryDisclosure(_TestServerBase):
    """BT-030: durable Operation projection follows role disclosure policy."""

    def _issued(self, role):
        import repositories as repo
        import services as svc
        auth = svc.AuthenticationService(repo.AuthRepository(lambda: self._db), registration_secret="ops-proof")
        registration = auth.request_registration(
            device_name=f"{role} operations", device_identity=f"ops-{role}",
            requested_role=role, requested_scopes=None, registration_proof="ops-proof",
        )
        return auth.approve_registration(registration["uuid"])

    def _operation(self):
        import repositories as repo
        import services as svc
        ops = svc.OperationService(repo.OperationRepository(lambda: self._db))
        operation = ops.begin("repair", svc.OP_INITIATOR_SYSTEM, entity_uuid="album-1", summary="Repair needs review")
        return ops.mark_needs_repair(operation["uuid"], "filesystem", "filesystem.write-failed", error_details="/private/archive/a raw stack trace", recovery_context="Confirm path and retry.")

    def test_reader_sees_only_public_summary(self):
        operation = self._operation(); issued = self._issued("reader")
        status, body = self._get(f"/api/v1/operations/{operation['uuid']}", {"Authorization": f"Bearer {issued['token']}"})
        self.assertEqual(200, status); item = body["data"]["operation"]
        self.assertEqual(operation["uuid"], item["uuid"])
        self.assertNotIn("recovery_context", item); self.assertNotIn("error_details", item)

    def test_writer_gets_operational_context_but_not_sensitive_details(self):
        operation = self._operation(); issued = self._issued("writer")
        status, body = self._get("/api/v1/operations", {"Authorization": f"Bearer {issued['token']}"})
        self.assertEqual(200, status); item = next(x for x in body["data"]["items"] if x["uuid"] == operation["uuid"])
        self.assertEqual("Confirm path and retry.", item["recovery_context"])
        self.assertNotIn("error_details", item)

    def test_unversioned_operation_history_is_not_exposed(self):
        self._operation(); status, body = self._get("/api/operations")
        self.assertEqual(404, status); self.assertEqual("NOT_FOUND", body["error"]["code"])


if __name__ == "__main__":
    unittest.main()
