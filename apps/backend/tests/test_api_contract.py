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
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
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
    remark TEXT,
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
    album_id INTEGER,
    lifecycle_state TEXT NOT NULL DEFAULT 'active',
    archive_classification TEXT,
    archive_reason TEXT,
    archived_at TEXT,
    archive_operation_uuid TEXT
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

    def _get_raw(self, path: str, headers: dict | None = None):
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        conn.request("GET",path,headers=headers or {}); resp = conn.getresponse()
        status, content_type, cache, body = resp.status,resp.getheader("Content-Type"),resp.getheader("Cache-Control"),resp.read()
        conn.close(); return status,content_type,cache,body

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

    def _put(self, path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(payload).encode()
        conn = HTTPConnection("127.0.0.1", self._port, timeout=5)
        request_headers = {"Content-Type": "application/json"}; request_headers.update(headers or {})
        conn.request("PUT", path, body=data, headers=request_headers)
        resp = conn.getresponse(); body = json.loads(resp.read().decode()); conn.close()
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

    def test_historical_workspace_active_client_api_is_retired(self):
        reader, writer = self._bearer(self._issue(role="reader")), self._bearer(self._issue(role="writer"))
        status, body = self._get("/api/v1/workspace/albums", reader)
        self.assertEqual(410, status); self.assertEqual("HISTORICAL_WORKSPACE_RETIRED", body["error"]["code"])
        status, body = self._put("/api/v1/workspace/albums/1", {"remark": "revive"}, writer)
        self.assertEqual(410, status); self.assertEqual("HISTORICAL_WORKSPACE_RETIRED", body["error"]["code"])
        status, body = self._post("/api/v1/workspace/albums/batch", {"ids": [1], "changes": {"remark": "revive"}}, writer)
        self.assertEqual(410, status); self.assertEqual("HISTORICAL_WORKSPACE_RETIRED", body["error"]["code"])

    def test_historical_workspace_audit_is_admin_only_redacted_and_terminal(self):
        marker = self._db.execute("SELECT COUNT(*) FROM workspace_album").fetchone()[0]
        self._db.execute("""INSERT INTO workspace_album
            (uuid, album_name, current_path, expected_path, ai_result, lifecycle_state,
             archive_classification, archive_operation_uuid)
            VALUES (?, 'Historical', '/secret/source', '/secret/target', '{"raw":true}',
                    'archived_retired', 'already_materialized', 'op-history')""", (f"history-{marker}",))
        history_id = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]; self._db.commit()
        status, denied = self._get("/api/v1/admin/history/workspace-albums", self._bearer(self._issue(role="reader")))
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_INSUFFICIENT_SCOPE", denied["error"]["code"])
        admin = self._bearer(self._issue(role="admin"))
        status, listing = self._get("/api/v1/admin/history/workspace-albums", admin)
        self.assertEqual(200, status); item = next(x for x in listing["data"] if x["id"] == history_id)
        self.assertEqual("archived_retired", item["lifecycle_state"])
        self.assertNotIn("current_path", item); self.assertNotIn("expected_path", item); self.assertNotIn("ai_result", item)
        status, detail = self._get(f"/api/v1/admin/history/workspace-albums/{history_id}", admin)
        self.assertEqual(200, status); self.assertEqual("op-history", detail["data"]["item"]["archive_operation_uuid"])

    def test_ai_workspace_container_is_admin_only_versioned_and_separate(self):
        status, denied = self._get("/api/v1/ai-workspaces", self._bearer(self._issue(role="writer")))
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_INSUFFICIENT_SCOPE", denied["error"]["code"])
        admin = self._bearer(self._issue(role="admin"))
        status, created = self._post("/api/v1/ai-workspaces", {"title": "API Album Analysis"}, admin)
        self.assertEqual(201, status); workspace = created["data"]["workspace"]
        self.assertEqual("Open", workspace["lifecycle_state"]); self.assertEqual("album_analysis", workspace["dataset_type"])
        status, preflight = self._get(f"/api/v1/ai-workspaces/{workspace['uuid']}/closure-preflight",admin)
        self.assertEqual(200,status); self.assertTrue(preflight["data"]["preflight"]["can_close"])
        status, closed = self._post(f"/api/v1/ai-workspaces/{workspace['uuid']}/close", {"expected_version": 1,"reason":"No dispatched work"}, admin)
        self.assertEqual(200, status); self.assertEqual("Closed", closed["data"]["workspace"]["lifecycle_state"])
        status, stale = self._post(f"/api/v1/ai-workspaces/{workspace['uuid']}/archive", {"expected_version": 1,"reason":"Stale archive"}, admin)
        self.assertEqual(409, status); self.assertEqual("AI_WORKSPACE_STALE", stale["error"]["code"])
        status, archived = self._post(f"/api/v1/ai-workspaces/{workspace['uuid']}/archive", {"expected_version": 2,"reason":"Retain audit history"}, admin)
        self.assertEqual(200, status); self.assertEqual("Archived", archived["data"]["workspace"]["lifecycle_state"])
        self.assertEqual("IndefiniteAudit",archived["data"]["workspace"]["retention"]["retention_classification"])
        self.assertEqual(0, self._db.execute("SELECT COUNT(*) FROM workspace_album WHERE uuid=?", (workspace["uuid"],)).fetchone()[0])

    def test_ai_model_configuration_admin_mutation_writer_discovery_and_disable(self):
        payload = {"name":"API Qwen Fast", "model_identifier":"qwen-vl", "model_repository":"ggml-org/qwen",
            "model_file":"qwen-q4.gguf", "vision_prompt_version":"vision-v1", "writer_prompt_version":"writer-v1",
            "sample_count":8, "context_size":4096, "threads":8, "gpu_layers":40, "max_tokens":800,
            "temperature":0.2, "image_max_tokens":384, "additional_parameters":{"batch_size":128}}
        writer = self._bearer(self._issue(role="writer")); admin = self._bearer(self._issue(role="admin"))
        status, denied = self._post("/api/v1/ai-model-configurations", payload, writer)
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_ADMIN_REQUIRED", denied["error"]["code"])
        status, created = self._post("/api/v1/ai-model-configurations", payload, admin)
        self.assertEqual(201, status); item = created["data"]["configuration"]
        status, visible = self._get("/api/v1/ai-model-configurations", writer)
        self.assertEqual(200, status); self.assertTrue(any(x["uuid"] == item["uuid"] for x in visible["data"]["items"]))
        status, updated = self._put(f"/api/v1/ai-model-configurations/{item['uuid']}", {"expected_version":1,"temperature":0.4}, admin)
        self.assertEqual(200, status); self.assertEqual(0.4, updated["data"]["configuration"]["temperature"])
        status, disabled = self._post(f"/api/v1/ai-model-configurations/{item['uuid']}/disable", {"expected_version":2}, admin)
        self.assertEqual(200, status); self.assertFalse(disabled["data"]["configuration"]["enabled"])
        status, hidden = self._get(f"/api/v1/ai-model-configurations/{item['uuid']}", writer)
        self.assertEqual(404, status); self.assertEqual("NOT_FOUND", hidden["error"]["code"])

    def test_ai_work_item_claim_ownership_failure_and_retry(self):
        marker = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        self._db.execute("INSERT INTO album (uuid,title,path) VALUES (?,?,?)", (f"worker-album-{marker}","Worker Album",f"Studio/Worker-{marker}"))
        album_id = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]; self._db.commit()
        admin = self._bearer(self._issue(role="admin")); first = self._bearer(self._issue(role="writer")); second = self._bearer(self._issue(role="writer"))
        config = {"name":f"Worker Config {marker}","model_identifier":"qwen","model_file":"qwen.gguf",
            "vision_prompt_version":"v1","writer_prompt_version":"w1","sample_count":8,"context_size":4096,
            "threads":8,"gpu_layers":40,"max_tokens":800,"temperature":0.2,"image_max_tokens":384}
        _, config_body = self._post("/api/v1/ai-model-configurations", config, admin); config_uuid = config_body["data"]["configuration"]["uuid"]
        _, workspace_body = self._post("/api/v1/ai-workspaces", {"title":f"Worker Queue {marker}"}, admin); workspace_uuid = workspace_body["data"]["workspace"]["uuid"]
        status, bypass = self._post(f"/api/v1/ai-workspaces/{workspace_uuid}/items", {"album_id":album_id,"configuration_uuid":config_uuid}, admin)
        self.assertEqual(409,status); self.assertEqual("WORK_DISPATCH_REQUIRED", bypass["error"]["code"])
        status, preview_body = self._post("/api/v1/work-dispatch/preview", {
            "worker_kind":"album_name_analysis","workspace_uuid":workspace_uuid,
            "configuration_uuids":[config_uuid],"album_ids":[album_id]}, admin)
        self.assertEqual(200,status)
        status, executed = self._post("/api/v1/work-dispatch/execute", {
            "preview_token":preview_body["data"]["preview"]["preview_token"]}, admin)
        self.assertEqual(200,status); dispatch_result = executed["data"]["result"]
        item_uuid = dispatch_result["groups"][0]["work_item_uuids"][0]
        status, batch_detail = self._get(f"/api/v1/work-dispatch/batches/{dispatch_result['batch_uuid']}", admin)
        self.assertEqual(200,status); self.assertEqual("Succeeded", batch_detail["data"]["operation"]["status"])
        status, replay = self._post("/api/v1/work-dispatch/execute", {
            "preview_token":preview_body["data"]["preview"]["preview_token"]}, admin)
        self.assertEqual(409,status); self.assertEqual("DISPATCH_PREVIEW_REPLAYED", replay["error"]["code"])
        status, claimed = self._post("/api/v1/ai-work-items/claim", {"lease_seconds":60}, first)
        self.assertEqual(200,status); self.assertEqual(item_uuid, claimed["data"]["item"]["uuid"])
        status, wrong = self._post(f"/api/v1/ai-work-items/{item_uuid}/heartbeat", {"lease_seconds":60}, second)
        self.assertEqual(409,status); self.assertEqual("AI_WORK_ITEM_CLAIM_INVALID", wrong["error"]["code"])
        status, failed = self._post(f"/api/v1/ai-work-items/{item_uuid}/fail", {"error_code":"MODEL_TIMEOUT","message":"timed out"}, first)
        self.assertEqual(200,status); failed_item = failed["data"]["item"]
        status, retried = self._post(f"/api/v1/ai-work-items/{item_uuid}/retry", {"expected_version":failed_item["version"]}, admin)
        self.assertEqual(200,status); self.assertEqual("Pending", retried["data"]["item"]["run_state"])
        status, claimed_again = self._post("/api/v1/ai-work-items/claim", {"lease_seconds":60}, second)
        self.assertEqual(200,status); self.assertEqual(2, claimed_again["data"]["item"]["attempt_count"])
        status, detail = self._get(f"/api/v1/ai-work-items/{item_uuid}", admin)
        self.assertEqual(200,status); self.assertEqual(2, len(detail["data"]["item"]["attempts"]))

    def test_work_dispatch_candidates_and_preview_are_admin_only_and_zero_write(self):
        marker = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        self._db.execute("""INSERT INTO album (uuid,title,rating,updated_at,created_at)
            VALUES (?,?,?,?,?)""", (f"dispatch-preview-{marker}", f"Dispatch Preview {marker}", 5,
                "2026-08-10", "2026-08-10"))
        album_id = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]; self._db.commit()
        writer = self._bearer(self._issue(role="writer")); admin_issue = self._issue(role="admin")
        admin = self._bearer(admin_issue)
        status, denied = self._get("/api/v1/work-dispatch/candidates?worker_kind=album_name_analysis", writer)
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_INSUFFICIENT_SCOPE", denied["error"]["code"])
        status, candidates = self._get(
            f"/api/v1/work-dispatch/candidates?worker_kind=album_name_analysis&q=Dispatch%20Preview%20{marker}", admin)
        self.assertEqual(200, status); self.assertTrue(any(item["id"] == album_id for item in candidates["data"]))

        config = {"name":f"Dispatch Preview Config {marker}","model_identifier":"qwen","model_file":"qwen.gguf",
            "vision_prompt_version":"v1","writer_prompt_version":"w1","sample_count":8,"context_size":4096,
            "threads":8,"gpu_layers":40,"max_tokens":800,"temperature":0.2,"image_max_tokens":384}
        _, config_body = self._post("/api/v1/ai-model-configurations", config, admin)
        _, workspace_body = self._post("/api/v1/ai-workspaces", {"title":f"Dispatch Preview Workspace {marker}"}, admin)
        before = {table:self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("work_dispatch_batch","work_dispatch_group","album_work_reservation","operation")}
        status, preview_body = self._post("/api/v1/work-dispatch/preview", {
            "worker_kind":"album_name_analysis", "workspace_uuid":workspace_body["data"]["workspace"]["uuid"],
            "configuration_uuids":[config_body["data"]["configuration"]["uuid"]], "album_ids":[album_id]}, admin)
        self.assertEqual(200, status); preview = preview_body["data"]["preview"]
        self.assertIn("preview_token", preview); self.assertEqual(1, preview["summary"]["work_items"])
        after = {table:self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in before}
        self.assertEqual(before, after)
        status, invalid = self._post("/api/v1/work-dispatch/preview", {
            "worker_kind":"album_name_analysis", "workspace_uuid":workspace_body["data"]["workspace"]["uuid"],
            "configuration_uuids":[config_body["data"]["configuration"]["uuid"]], "first_n":101}, admin)
        self.assertEqual(400, status); self.assertEqual("REQUEST_INVALID", invalid["error"]["code"])

    def test_photo_evidence_manifest_is_admin_selected_and_path_redacted(self):
        import server as srv
        marker = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        with tempfile.TemporaryDirectory() as root:
            album_dir = Path(root) / "manifest-album"; album_dir.mkdir()
            for index in range(10):
                (album_dir / f"sample-{index:02d}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([index])*(1000+index*100))
            self._db.execute("INSERT INTO album (uuid,title,path,updated_at) VALUES (?,?,?,?)",
                (f"manifest-{marker}","Manifest Album","manifest-album","v1"))
            album_id = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]; self._db.commit()
            admin = self._bearer(self._issue(role="admin")); writer_issued = self._issue(role="writer")
            writer = self._bearer(writer_issued); other_writer = self._bearer(self._issue(role="writer"))
            config = {"name":f"Manifest Config {marker}","model_identifier":"qwen","model_file":"qwen.gguf",
                "vision_prompt_version":"v1","writer_prompt_version":"w1","sample_count":8,"context_size":4096,
                "threads":8,"gpu_layers":40,"max_tokens":800,"temperature":0.2,"image_max_tokens":384}
            _, cfg = self._post("/api/v1/ai-model-configurations",config,admin)
            _, ws = self._post("/api/v1/ai-workspaces",{"title":f"Manifest WS {marker}"},admin)
            _, preview = self._post("/api/v1/work-dispatch/preview",{"worker_kind":"album_name_analysis",
                "workspace_uuid":ws["data"]["workspace"]["uuid"],"configuration_uuids":[cfg["data"]["configuration"]["uuid"]],
                "album_ids":[album_id]},admin)
            _, executed = self._post("/api/v1/work-dispatch/execute",{"preview_token":preview["data"]["preview"]["preview_token"]},admin)
            item_uuid = executed["data"]["result"]["groups"][0]["work_item_uuids"][0]
            group_uuid = executed["data"]["result"]["groups"][0]["group_uuid"]
            workspace_uuid = ws["data"]["workspace"]["uuid"]
            configuration_uuid = cfg["data"]["configuration"]["uuid"]
            status, kinds = self._get("/api/v1/work-dispatch/worker-kinds",admin)
            self.assertEqual(200,status)
            self.assertEqual("album_name_analysis",kinds["data"]["items"][0]["worker_kind"])
            status, denied = self._get("/api/v1/work-dispatch/worker-kinds",writer)
            self.assertEqual(403,status)
            status, active_groups = self._get(
                f"/api/v1/work-dispatch/groups?view=active&workspace_uuid={workspace_uuid}&limit=1&offset=0",admin)
            self.assertEqual(200,status)
            self.assertEqual(1,active_groups["meta"]["pagination"]["total"])
            self.assertEqual(group_uuid,active_groups["data"][0]["uuid"])
            self.assertIn("allowed_actions",active_groups["data"][0])
            status, overview = self._get(f"/api/v1/ai-workspaces/{workspace_uuid}/overview",admin)
            self.assertEqual(200,status)
            self.assertEqual(1,overview["data"]["overview"]["summary"]["total_groups"])
            self.assertIn("dispatch",overview["data"]["overview"]["allowed_actions"])
            with patch.object(srv,"APP_CONFIG",{**srv.APP_CONFIG,"archive_root":root}):
                status, denied = self._get(f"/api/v1/ai-work-items/{item_uuid}/evidence-manifest",writer)
                self.assertEqual(403,status)
                status, created = self._post(f"/api/v1/ai-work-items/{item_uuid}/evidence-manifest",{},admin)
                self.assertEqual(201,status); manifest = created["data"]["manifest"]
                self.assertEqual(8,len(manifest["evidence"])); self.assertNotIn(root,str(manifest))
                status, fetched = self._get(f"/api/v1/ai-work-items/{item_uuid}/evidence-manifest",admin)
                self.assertEqual(200,status); self.assertEqual(manifest["uuid"],fetched["data"]["manifest"]["uuid"])
                evidence_uuid = manifest["evidence"][0]["uuid"]
                self._db.execute("""UPDATE workspace_album_ai_worker SET run_state='Claimed',claimed_by_token_uuid=?,
                    lease_expires_at='2099-01-01T00:00:00+00:00' WHERE uuid=?""",
                    (writer_issued["token_record"]["uuid"],item_uuid)); self._db.commit()
                status, forbidden = self._get(f"/api/v1/ai-evidence/{evidence_uuid}",other_writer)
                self.assertEqual(403,status); self.assertEqual("EVIDENCE_CLAIM_REQUIRED",forbidden["error"]["code"])
                status, metadata = self._get(f"/api/v1/ai-evidence/{evidence_uuid}",writer)
                self.assertEqual(200,status); self.assertNotIn("relative_path",metadata["data"]["evidence"])
                status,mime,cache,content = self._get_raw(f"/api/v1/ai-evidence/{evidence_uuid}/content",writer)
                self.assertEqual(200,status); self.assertEqual("image/jpeg",mime); self.assertEqual("private, no-store",cache)
                self.assertEqual((album_dir / manifest["evidence"][0]["relative_path"]).read_bytes(),content)
                vision = {"schema_version":"curator://album-analysis/vision/v1","payload":{
                    "scene":"A family beside a lake","people":{"minimum":3,"maximum":4},
                    "location_environment":"Outdoor lakeside","subjects":["family"],"objects":["trees"],
                    "actions":["walking"],"confidence":0.9,"warnings":[]}}
                status, accepted = self._post(f"/api/v1/ai-work-items/{item_uuid}/results/vision",vision,writer)
                self.assertEqual(200,status); self.assertEqual("Vision",accepted["data"]["result"]["stage"])
                writer_payload = {"schema_version":"curator://album-analysis/writer/v1","payload":{
                    "album_summary":"A calm family outing","description":"A family explores a lakeside setting.",
                    "suggested_names":["Lakeside Family Walk","Quiet Summer Shore","Morning By The Lake",
                        "Family Waterside Adventure","Gentle Lakeside Memories","Together Near The Water"]}}
                status, accepted = self._post(f"/api/v1/ai-work-items/{item_uuid}/results/writer",writer_payload,writer)
                self.assertEqual(200,status); self.assertEqual("Writer",accepted["data"]["result"]["stage"])
                status, results = self._get(f"/api/v1/ai-work-items/{item_uuid}/results",admin)
                self.assertEqual(200,status); self.assertEqual("ReadyForReview",results["data"]["results"]["state"]["state"])
                status, queue = self._get("/api/v1/ai-reviews?state=ReadyForReview",admin)
                self.assertEqual(200,status); self.assertTrue(any(row["work_item_uuid"]==item_uuid for row in queue["data"]))
                status, filtered_queue = self._get(
                    f"/api/v1/ai-reviews?album_id={album_id}&configuration_uuid={configuration_uuid}"
                    f"&group_uuid={group_uuid}&workspace_uuid={workspace_uuid}&q=Manifest&limit=1",admin)
                self.assertEqual(200,status)
                self.assertEqual([item_uuid],[row["work_item_uuid"] for row in filtered_queue["data"]])
                self.assertEqual(1,filtered_queue["meta"]["pagination"]["total"])
                status, started = self._post(f"/api/v1/ai-work-items/{item_uuid}/review/start",{"expected_version":1},admin)
                self.assertEqual(200,status); self.assertEqual("InReview",started["data"]["review"]["review"]["state"])
                status, approved = self._post(f"/api/v1/ai-work-items/{item_uuid}/review/decision",{
                    "expected_version":2,"action":"approve","rating":5,"notes":"Good result",
                    "selection_source":"Recommendation","selected_name":"Lakeside Family Walk"},admin)
                self.assertEqual(200,status); self.assertEqual("Approved",approved["data"]["review"]["review"]["state"])
                status, detail = self._get(f"/api/v1/ai-work-items/{item_uuid}/review",admin)
                self.assertEqual(200,status); self.assertEqual("Lakeside Family Walk",detail["data"]["review"]["review"]["selected_name"])
                status, promotion_preview = self._post(f"/api/v1/ai-work-items/{item_uuid}/promotion/preview",{},admin)
                self.assertEqual(200,status); promotion_preview=promotion_preview["data"]["preview"]
                self.assertEqual("Lakeside Family Walk",promotion_preview["resulting"]["title"])
                status, promoted = self._post("/api/v1/ai-promotions/execute",{
                    "preview_token":promotion_preview["preview_token"],"confirmation":promotion_preview["confirmation"]},admin)
                self.assertEqual(200,status); self.assertEqual("Promoted",promoted["data"]["promotion"]["outcome"])
                self.assertEqual("Lakeside Family Walk",self._db.execute("SELECT title FROM album WHERE id=?",(album_id,)).fetchone()[0])
                status, promotion_history = self._get(f"/api/v1/ai-work-items/{item_uuid}/promotion",admin)
                self.assertEqual(200,status)
                self.assertEqual("Promoted",promotion_history["data"]["promotion_history"]["items"][0]["outcome"])
                status, traceability = self._get(f"/api/v1/ai-work-items/{item_uuid}/review",admin)
                self.assertEqual(200,status)
                review_projection = traceability["data"]["review"]
                self.assertEqual(1,len(review_projection["promotions"]))
                self.assertTrue(review_projection["operations"])
                self.assertEqual(8,len(review_projection["evidence_history"]["evidence"]))
                self.assertNotIn(root,str(review_projection))
                self.assertNotIn("error_details",str(review_projection))
                status, group_detail = self._get(f"/api/v1/work-dispatch/groups/{group_uuid}",admin)
                self.assertEqual(200,status); self.assertIn("release",group_detail["data"]["group"]["allowed_actions"])
                status, released = self._post(f"/api/v1/work-dispatch/groups/{group_uuid}/release",{
                    "expected_version":1,"reason":"Promotion completed"},admin)
                self.assertEqual(200,status); self.assertEqual("Closed",released["data"]["closure"]["disposition"])
                status, history = self._get(f"/api/v1/work-dispatch/history?album_id={album_id}",admin)
                self.assertEqual(200,status); self.assertEqual("Released",history["data"]["items"][0]["group_state"])
                status, history_groups = self._get(
                    f"/api/v1/work-dispatch/groups?view=history&album_id={album_id}",admin)
                self.assertEqual(200,status)
                self.assertEqual(group_uuid,history_groups["data"][0]["uuid"])
                self.assertEqual("Closed",history_groups["data"][0]["disposition"])
                (album_dir / manifest["evidence"][0]["relative_path"]).unlink()
                status, evidence_history = self._get(f"/api/v1/ai-work-items/{item_uuid}/evidence-history",admin)
                self.assertEqual(200,status); self.assertEqual(1,evidence_history["data"]["evidence_history"]["availability_counts"]["Missing"])
                status, candidates = self._get("/api/v1/work-dispatch/candidates?worker_kind=album_name_analysis&availability=available",admin)
                self.assertEqual(200,status); self.assertTrue(any(row["id"]==album_id for row in candidates["data"]))
                _, redispatch_preview = self._post("/api/v1/work-dispatch/preview",{"worker_kind":"album_name_analysis",
                    "workspace_uuid":ws["data"]["workspace"]["uuid"],"configuration_uuids":[cfg["data"]["configuration"]["uuid"]],
                    "album_ids":[album_id]},admin)
                status, redispatched = self._post("/api/v1/work-dispatch/execute",{
                    "preview_token":redispatch_preview["data"]["preview"]["preview_token"]},admin)
                self.assertEqual(200,status); self.assertNotEqual(group_uuid,redispatched["data"]["result"]["groups"][0]["group_uuid"])

    def test_current_principal_and_renewal_request_are_token_safe(self):
        issued = self._issue(role="writer")
        headers = self._bearer(issued)
        status, body = self._get("/api/v1/auth/me", headers)
        self.assertEqual(status, 200)
        principal = body["data"]["principal"]
        self.assertEqual(principal["role"], "writer")
        self.assertEqual(principal["scopes"], ["read", "write"])
        self.assertNotIn("token", principal)
        self.assertNotIn("token_hash", principal)
        import repositories as repo
        registration = repo.AuthRepository(lambda: self._db).get_registration(principal["registration_uuid"])
        status, renewal = self._post(
            "/api/v1/auth/renewals",
            {"device_identity": registration["device_identity"]}, headers,
        )
        self.assertEqual(status, 202)
        renewal_uuid = renewal["data"]["renewal"]["uuid"]
        status, refreshed = self._get("/api/v1/auth/me", headers)
        self.assertEqual(status, 200)
        self.assertEqual(refreshed["data"]["principal"]["renewal"]["uuid"], renewal_uuid)
        status, duplicate = self._post(
            "/api/v1/auth/renewals",
            {"device_identity": registration["device_identity"]}, headers,
        )
        self.assertEqual(status, 409)
        self.assertEqual(duplicate["error"]["code"], "BUSINESS_CONFLICT")

    def test_album_batch_preview_execute_and_stale_contract(self):
        issued = self._issue(role="writer")
        headers = self._bearer(issued)
        marker = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        self._db.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (f"batch-{marker}-1", f"Batch {marker} One", "2024-01-01", "2024-01-01"),
        )
        first = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]
        self._db.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (f"batch-{marker}-2", f"Batch {marker} Two", "2024-01-01", "2024-01-01"),
        )
        second = self._db.execute("SELECT last_insert_rowid()").fetchone()[0]
        self._db.commit()
        status, body = self._post(
            "/api/v1/albums/batch/preview",
            {"ids": [first, second], "changes": {"rating": 4}}, headers,
        )
        self.assertEqual(status, 200)
        preview = body["data"]["preview"]
        self.assertEqual(preview["summary"]["eligible"], 2)
        self.assertEqual(
            self._db.execute("SELECT COUNT(*) FROM album WHERE rating = 4").fetchone()[0], 0
        )
        status, executed = self._post(
            "/api/v1/albums/batch/execute", {"preview_token": preview["preview_token"]}, headers,
        )
        self.assertEqual(status, 200)
        self.assertEqual(executed["data"]["result"]["summary"]["succeeded"], 2)
        self.assertIsNotNone(executed["data"]["result"]["operation_uuid"])

        status, stale_preview = self._post(
            "/api/v1/albums/batch/preview",
            {"ids": [first, second], "changes": {"rating": 5}, "overwrite_non_empty": True}, headers,
        )
        self.assertEqual(status, 200)
        self._db.execute("UPDATE album SET updated_at = '2030-01-01' WHERE id = ?", (second,))
        self._db.commit()
        status, stale = self._post(
            "/api/v1/albums/batch/execute",
            {"preview_token": stale_preview["data"]["preview"]["preview_token"]}, headers,
        )
        self.assertEqual(status, 409)
        self.assertEqual(stale["error"]["code"], "ALBUM_BATCH_STALE")
        self.assertEqual(self._db.execute("SELECT rating FROM album WHERE id = ?", (first,)).fetchone()[0], 4)

    def test_album_relationship_errors_are_structured(self):
        issued = self._issue(role="writer")
        status, body = self._post(
            "/api/v1/albums",
            {"title": "Invalid relationship", "models": [{"model_id": 999999}]},
            self._bearer(issued),
        )
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "REQUEST_INVALID")

        status, body = self._post(
            "/api/v1/albums",
            {"title": "Duplicate relationship", "models": [{"model_id": 1}, {"model_id": 1}]},
            self._bearer(issued),
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "ALBUM_MODEL_DUPLICATE")


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
        import repositories as repo
        import server as srv
        import services as svc
        auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self._db),
            operation_service=svc.OperationService(repo.OperationRepository(lambda: self._db)),
        )
        admin = auth.bootstrap_first_admin(device_name="API Admin", device_identity="api-admin")
        with patch.object(srv, "AUTH_REGISTRATION_SECRET", "test-proof"):
            status, body = self._post("/api/auth/registrations", {
                "device_name": "workflow worker", "device_identity": "workflow-worker-1",
                "requested_role": "writer", "requested_scopes": ["read", "write"],
                "registration_proof": "test-proof",
            })
            self.assertEqual(201, status)
            registration = body["data"]["registration"]
            self.assertEqual("PendingApproval", registration["status"])
            status, issued_body = self._post(
                f"/api/v1/auth/registrations/{registration['uuid']}/approve", {},
                {"Authorization": f"Bearer {admin['token']}"},
            )
        self.assertEqual(200, status)
        issued = issued_body["data"]
        self.assertIn("token", issued)
        self.assertNotIn("token_hash", issued["token_record"])
        headers = {"Authorization": f"Bearer {issued['token']}"}
        status, preview = self._post("/api/v1/import/preview", {
            "items": [{"model_name": "API Model", "album_name": "API Album", "studio_name": "API Studio"}],
            "import_action": "DATABASE_ONLY",
        }, headers)
        self.assertEqual(200, status)
        self.assertIn("preview", preview["data"])
        self.assertIn("preview_token", preview["data"]["preview"])

    def test_import_execute_requires_valid_unreplayed_preview_token(self):
        import repositories as repo
        import services as svc
        marker = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self._db), registration_secret="import-proof"
        )
        registration = auth.request_registration(
            device_name="Import Writer", device_identity=f"import-writer-{marker}",
            requested_role="writer", requested_scopes=None,
            registration_proof="import-proof",
        )
        issued = auth.approve_registration(registration["uuid"])
        headers = {"Authorization": f"Bearer {issued['token']}"}
        status, preview = self._post("/api/v1/import/preview", {
            "items": [{"model_name": f"Token Model {marker}", "album_name": f"Token Album {marker}", "studio_name": "Token Studio"}],
            "import_action": "DATABASE_ONLY",
        }, headers)
        self.assertEqual(status, 200)
        token = preview["data"]["preview"]["preview_token"]
        status, tampered = self._post("/api/v1/import/execute", {"preview_token": token + "x"}, headers)
        self.assertEqual(status, 409)
        self.assertEqual(tampered["error"]["code"], "IMPORT_PREVIEW_INVALID")
        status, executed = self._post("/api/v1/import/execute", {"preview_token": token}, headers)
        self.assertEqual(status, 200)
        self.assertEqual(executed["data"]["summary"]["created"], 1)
        status, replay = self._post("/api/v1/import/execute", {"preview_token": token}, headers)
        self.assertEqual(status, 409)
        self.assertEqual(replay["error"]["code"], "IMPORT_PREVIEW_REPLAYED")

    def test_rejected_import_request_has_no_business_side_effect(self):
        before = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        status, body = self._post("/api/v1/import/preview", {"items": []})
        self.assertEqual(401, status)
        self.assertEqual("AUTHENTICATION_MISSING_TOKEN", body["error"]["code"])
        after = self._db.execute("SELECT COUNT(*) FROM album").fetchone()[0]
        self.assertEqual(before, after)


class TestAdministratorBootstrapApi(_TestServerBase):
    """UI-004B: loopback Code is required and legacy approval is closed."""

    def _code(self):
        import repositories as repo
        import services as svc
        return svc.AuthenticationService(repo.AuthRepository(lambda: self._db)).create_bootstrap_code()

    def test_status_and_successful_completion_disclose_token_once(self):
        status, body = self._get("/api/auth/bootstrap/status")
        self.assertEqual(status, 200)
        self.assertFalse(body["data"]["bootstrap"]["initialized"])
        code = self._code()
        status, body = self._post("/api/auth/bootstrap/complete", {
            "code": code["code"], "device_name": "Browser Admin", "device_identity": "browser-admin",
        })
        self.assertEqual(status, 200)
        token = body["data"]["token"]
        self.assertTrue(token)
        self.assertNotIn("token_hash", body["data"]["token_record"])
        status, replay = self._post("/api/auth/bootstrap/complete", {
            "code": code["code"], "device_name": "Replay", "device_identity": "replay",
        })
        self.assertEqual(status, 409)
        self.assertEqual(replay["error"]["code"], "AUTHENTICATION_BOOTSTRAP_CLOSED")

    def test_legacy_unauthenticated_approval_is_rejected(self):
        status, body = self._post("/api/auth/registrations/not-approved/approve", {})
        self.assertEqual(status, 403)
        self.assertEqual(body["error"]["code"], "AUTHORIZATION_ADMIN_REQUIRED")

    def test_non_loopback_status_is_rejected_before_reading_state(self):
        import server as srv
        handler = object.__new__(srv.AppHandler)
        handler.client_address = ("192.0.2.10", 12345)
        captured = {}
        handler._send_error = lambda status, code, message: captured.update(status=status, code=code)
        handler._handle_auth_bootstrap_status()
        self.assertEqual(captured, {"status": 403, "code": "AUTHORIZATION_LOOPBACK_REQUIRED"})


class TestOperationHistoryDisclosure(_TestServerBase):
    """BT-030: durable Operation projection follows role disclosure policy."""

    def _issued(self, role):
        import repositories as repo
        import services as svc
        auth = svc.AuthenticationService(repo.AuthRepository(lambda: self._db), registration_secret="ops-proof")
        registration = auth.request_registration(
            device_name=f"{role} operations", device_identity=f"ops-{role}-{self._testMethodName}",
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
        self.assertEqual(200, status); item = next(x for x in body["data"] if x["uuid"] == operation["uuid"])
        self.assertEqual("Confirm path and retry.", item["recovery_context"])
        self.assertNotIn("error_details", item)

    def test_query_filters_and_stable_keyset_pagination(self):
        import repositories as repo
        issued = self._issued("writer")
        repository = repo.OperationRepository(lambda: self._db)
        for index in range(4):
            repository.create({
                "uuid": f"bt037-{index}", "operation_type": "bt037_import",
                "initiator": "System", "status": "Succeeded" if index != 1 else "Failed",
                "started_at": f"2026-08-0{index + 1}T00:00:00+00:00",
                "summary": f"BT-037 fixture {index}",
            })
        headers = {"Authorization": f"Bearer {issued['token']}"}
        status, first = self._get(
            "/api/v1/operations?operation_type=bt037_import&limit=2", headers,
        )
        self.assertEqual(200, status)
        self.assertEqual(["bt037-3", "bt037-2"], [item["uuid"] for item in first["data"]])
        self.assertEqual(4, first["meta"]["pagination"]["total"])
        self.assertTrue(first["meta"]["pagination"]["has_more"])
        cursor = first["meta"]["pagination"]["next_cursor"]

        repository.create({
            "uuid": "bt037-newer", "operation_type": "bt037_import",
            "initiator": "System", "status": "Succeeded",
            "started_at": "2026-08-09T00:00:00+00:00",
        })
        status, second = self._get(
            f"/api/v1/operations?operation_type=bt037_import&limit=2&cursor={cursor}", headers,
        )
        self.assertEqual(200, status)
        self.assertEqual(["bt037-1", "bt037-0"], [item["uuid"] for item in second["data"]])
        self.assertFalse(second["meta"]["pagination"]["has_more"])

        status, filtered = self._get(
            "/api/v1/operations?operation_type=bt037_import&status=Failed", headers,
        )
        self.assertEqual(200, status)
        self.assertEqual(["bt037-1"], [item["uuid"] for item in filtered["data"]])

    def test_query_rejects_invalid_or_filter_mismatched_cursor(self):
        issued = self._issued("reader")
        headers = {"Authorization": f"Bearer {issued['token']}"}
        status, malformed = self._get("/api/v1/operations?cursor=not-a-cursor", headers)
        self.assertEqual(400, status)
        self.assertEqual("REQUEST_INVALID", malformed["error"]["code"])

        status, first = self._get("/api/v1/operations?limit=1", headers)
        self.assertEqual(200, status)
        cursor = first["meta"]["pagination"]["next_cursor"]
        self.assertTrue(cursor)
        status, mismatch = self._get(
            f"/api/v1/operations?limit=1&status=Succeeded&cursor={cursor}", headers,
        )
        self.assertEqual(400, status)
        self.assertEqual("REQUEST_INVALID", mismatch["error"]["code"])

    def test_query_rejects_invalid_limits_dates_and_status(self):
        issued = self._issued("reader")
        headers = {"Authorization": f"Bearer {issued['token']}"}
        for query in ("limit=0", "limit=101", "limit=no", "status=Unknown",
                      "started_from=not-a-date",
                      "started_from=2026-08-09T00:00:00Z&started_to=2026-08-01T00:00:00Z"):
            status, body = self._get(f"/api/v1/operations?{query}", headers)
            self.assertEqual(400, status, query)
            self.assertEqual("REQUEST_INVALID", body["error"]["code"])

    def test_unversioned_operation_history_is_not_exposed(self):
        self._operation(); status, body = self._get("/api/operations")
        self.assertEqual(404, status); self.assertEqual("NOT_FOUND", body["error"]["code"])


class TestIssueRepairDecisionApi(_TestServerBase):
    """BT-038 authenticated review, disclosure, optimistic decision contract."""

    def _issued(self, role):
        import repositories as repo
        import services as svc
        auth = svc.AuthenticationService(repo.AuthRepository(lambda: self._db), registration_secret="bt038-proof")
        registration = auth.request_registration(
            device_name=f"BT038 {role}", device_identity=f"bt038-{role}-{self._testMethodName}",
            requested_role=role, requested_scopes=None, registration_proof="bt038-proof",
        )
        return auth.approve_registration(registration["uuid"])

    def _headers(self, role):
        return {"Authorization": f"Bearer {self._issued(role)['token']}"}

    def _issue(self):
        import repositories as repo
        import services as svc
        return svc.IssueService(repo.IssueRepository(lambda: self._db)).create({
            "category": "Repair", "description": "BT038 issue",
            "source_workflow": "test", "suggested_resolution": "Review",
        })

    def _repair(self):
        import repositories as repo
        return repo.RepairRepository(lambda: self._db).create({
            "operation_uuid": "original-operation", "album_uuid": "album-bt038",
            "expected_path": "B/BT/Studio/Album", "category": "Assisted",
            "failure_reason": "Source move failed",
        })

    def test_issue_review_decision_and_stale_replay(self):
        issue, headers = self._issue(), self._headers("writer")
        status, listing = self._get("/api/v1/issues?state=Open", headers)
        self.assertEqual(200, status)
        item = next(row for row in listing["data"]["items"] if row["uuid"] == issue["uuid"])
        self.assertIn("begin_work", item["allowed_actions"])
        status, decided = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "begin_work", "expected_updated_at": item["updated_at"],
        }, headers)
        self.assertEqual(200, status)
        self.assertEqual("InProgress", decided["data"]["issue"]["state"])
        self.assertTrue(decided["data"]["operation_uuid"])
        status, stale = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "begin_work", "expected_updated_at": item["updated_at"],
        }, headers)
        self.assertEqual(409, status)
        self.assertIn(stale["error"]["code"], {"WORKFLOW_STALE", "INVALID_TRANSITION"})

    def test_admin_issue_resolution_and_writer_admin_boundary(self):
        issue = self._issue(); writer = self._headers("writer")
        status, begun = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "begin_work", "expected_updated_at": issue["updated_at"],
        }, writer)
        self.assertEqual(200, status)
        current = begun["data"]["issue"]
        status, denied = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "resolve", "expected_updated_at": current["updated_at"], "verification": "Checked",
        }, writer)
        self.assertEqual(409, status); self.assertEqual("INVALID_TRANSITION", denied["error"]["code"])
        admin = self._headers("admin")
        status, resolved = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "resolve", "expected_updated_at": current["updated_at"], "verification": "Archive verified",
        }, admin)
        self.assertEqual(200, status); self.assertEqual("Resolved", resolved["data"]["issue"]["state"])

    def test_repair_confirmation_start_and_reader_redaction(self):
        repair = self._repair(); reader = self._headers("reader")
        status, detail = self._get(f"/api/v1/repairs/{repair['uuid']}", reader)
        self.assertEqual(200, status); self.assertNotIn("expected_path", detail["data"]["repair"])
        writer = self._headers("writer")
        status, detail = self._get(f"/api/v1/repairs/{repair['uuid']}", writer)
        current = detail["data"]["repair"]
        self.assertEqual(200, status); self.assertEqual(["ignore", "escalate", "confirm"], current["allowed_actions"])
        status, confirmed = self._post(f"/api/v1/repairs/{repair['uuid']}/decisions", {
            "action": "confirm", "expected_updated_at": current["updated_at"],
            "confirmation": "I reviewed the candidate and evidence.",
        }, writer)
        self.assertEqual(200, status); confirmed_repair = confirmed["data"]["repair"]
        self.assertIn("start", confirmed_repair["allowed_actions"])
        status, started = self._post(f"/api/v1/repairs/{repair['uuid']}/decisions", {
            "action": "start", "expected_updated_at": confirmed_repair["updated_at"],
        }, writer)
        self.assertEqual(200, status); self.assertEqual("Repairing", started["data"]["repair"]["state"])

    def test_reader_cannot_submit_decision(self):
        issue, headers = self._issue(), self._headers("reader")
        status, body = self._post(f"/api/v1/issues/{issue['uuid']}/decisions", {
            "action": "begin_work", "expected_updated_at": issue["updated_at"],
        }, headers)
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_INSUFFICIENT_SCOPE", body["error"]["code"])

    def test_suppression_is_admin_only_bounded_and_audited(self):
        payload = {"fingerprint": "bt038-fingerprint", "scope_path": "B/BT/Studio/Album",
                   "reason": "Reviewed bounded exception",
                   "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        status, denied = self._post("/api/v1/repair-suppressions", payload, self._headers("writer"))
        self.assertEqual(403, status); self.assertEqual("AUTHORIZATION_ADMIN_REQUIRED", denied["error"]["code"])
        admin = self._headers("admin")
        status, created = self._post("/api/v1/repair-suppressions", payload, admin)
        self.assertEqual(201, status)
        record = created["data"]["suppression"]
        self.assertEqual(payload["scope_path"], record["scope_path"])
        self.assertTrue(record["operation_uuid"])
        status, listing = self._get("/api/v1/repair-suppressions", admin)
        self.assertEqual(200, status)
        self.assertTrue(any(item["uuid"] == record["uuid"] for item in listing["data"]["items"]))


class TestAuthenticationAdministrationApi(_TestServerBase):
    """BT-040 Admin state, bounded approval, renewal, and last-Admin safety."""

    def test_complete_admin_lifecycle_contract(self):
        import repositories as repo
        import services as svc
        repository = repo.AuthRepository(lambda: self._db)
        bootstrap = svc.AuthenticationService(repository).bootstrap_first_admin(
            device_name="BT040 Primary Admin", device_identity="bt040-primary-admin",
        )
        admin_headers = {"Authorization": f"Bearer {bootstrap['token']}"}
        requester = svc.AuthenticationService(repository, registration_secret="bt040-proof")
        writer = requester.request_registration(
            device_name="BT040 Writer", device_identity="bt040-writer",
            requested_role="writer", requested_scopes=["read", "write"], registration_proof="bt040-proof",
        )
        status, state = self._get("/api/v1/auth/admin/state", admin_headers)
        self.assertEqual(200, status)
        self.assertTrue(any(item["uuid"] == writer["uuid"] for item in state["data"]["registrations"]))
        self.assertNotIn("token_hash", json.dumps(state))

        status, elevated = self._post(f"/api/v1/auth/admin/registrations/{writer['uuid']}/approve", {
            "approved_role": "admin", "approved_scopes": ["read", "write", "admin"],
        }, admin_headers)
        self.assertEqual(409, status); self.assertEqual("AUTHORIZATION_ELEVATION_NOT_REQUESTED", elevated["error"]["code"])
        status, issued_writer = self._post(f"/api/v1/auth/admin/registrations/{writer['uuid']}/approve", {
            "approved_role": "writer", "approved_scopes": ["read", "write"],
        }, admin_headers)
        self.assertEqual(200, status); writer_token = issued_writer["data"]["token"]

        status, protected = self._post(
            f"/api/v1/auth/admin/tokens/{bootstrap['token_record']['uuid']}/revoke", {}, admin_headers,
        )
        self.assertEqual(409, status); self.assertEqual("LAST_USABLE_ADMIN", protected["error"]["code"])

        second_admin = requester.request_registration(
            device_name="BT040 Secondary Admin", device_identity="bt040-secondary-admin",
            requested_role="admin", requested_scopes=["read", "write", "admin"], registration_proof="bt040-proof",
        )
        status, issued_admin = self._post(f"/api/v1/auth/admin/registrations/{second_admin['uuid']}/approve", {}, admin_headers)
        self.assertEqual(200, status); secondary_headers = {"Authorization": f"Bearer {issued_admin['data']['token']}"}
        status, revoked = self._post(
            f"/api/v1/auth/admin/tokens/{bootstrap['token_record']['uuid']}/revoke", {}, secondary_headers,
        )
        self.assertEqual(200, status); self.assertEqual("Revoked", revoked["data"]["status"])

        renewal = svc.AuthenticationService(repository).request_renewal(
            writer_token, device_identity="bt040-writer",
        )
        status, renewed = self._post(f"/api/v1/auth/admin/renewals/{renewal['uuid']}/approve", {}, secondary_headers)
        self.assertEqual(200, status); self.assertTrue(renewed["data"]["token"])
        status, final_state = self._get("/api/v1/auth/admin/state", secondary_headers)
        self.assertEqual(200, status)
        serialized = json.dumps(final_state)
        self.assertNotIn(writer_token, serialized); self.assertNotIn("token_hash", serialized)


if __name__ == "__main__":
    unittest.main()
