#!/usr/bin/env python3
"""Focused service-layer tests for extracted business logic.

Each test class covers one service class.  Tests use an in-memory SQLite
database created via a factory so they run without any real database or
filesystem.  Business rules, workflow decisions, and transaction semantics are
verified here; HTTP transport concerns are verified in test_api_contract.py.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Make the tools/web_ui package importable.
sys.path.insert(0, str(Path(__file__).parent.parent))

import services as svc


# ---------------------------------------------------------------------------
# Shared test database schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
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
    uuid TEXT NOT NULL DEFAULT '',
    name TEXT,
    website TEXT,
    description TEXT,
    media_scope TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
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
    uuid TEXT NOT NULL DEFAULT '',
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


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _db_factory(conn: sqlite3.Connection):
    """Return a db-factory callable that always yields the same connection."""
    return lambda: conn


# ---------------------------------------------------------------------------
# StatusService
# ---------------------------------------------------------------------------

class TestStatusServiceDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute("INSERT INTO status (name) VALUES ('Active')")
        self.conn.commit()
        self.service = svc.StatusService(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_status_succeeds(self):
        self.service.delete(1)
        row = self.conn.execute("SELECT id FROM status WHERE id = 1").fetchone()
        self.assertIsNone(row)

    def test_delete_raises_conflict_when_album_references_status(self):
        self.conn.execute(
            "INSERT INTO album (uuid, status_id, title, created_at, updated_at)"
            " VALUES ('u1', 1, 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.delete(1)
        exc = ctx.exception
        self.assertEqual(exc.code, "BUSINESS_CONFLICT")
        self.assertGreater(exc.details["album_refs"], 0)

    def test_delete_raises_conflict_when_workspace_album_references_status(self):
        self.conn.execute(
            "INSERT INTO workspace_album (status_id) VALUES (1)"
        )
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.delete(1)
        exc = ctx.exception
        self.assertGreater(exc.details["workspace_album_refs"], 0)

    def test_conflict_details_include_both_ref_counts(self):
        self.conn.execute(
            "INSERT INTO album (uuid, status_id, title, created_at, updated_at)"
            " VALUES ('u2', 1, 'T2', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute("INSERT INTO workspace_album (status_id) VALUES (1)")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.delete(1)
        details = ctx.exception.details
        self.assertIn("album_refs", details)
        self.assertIn("workspace_album_refs", details)


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------

class TestModelServiceDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name) VALUES ('m1', 'Alice')"
        )
        self.conn.commit()
        self.service = svc.ModelService(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_model_succeeds(self):
        self.service.delete(1)
        self.assertIsNone(
            self.conn.execute("SELECT id FROM model WHERE id = 1").fetchone()
        )

    def test_delete_raises_conflict_when_album_model_exists(self):
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'A', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.delete(1)
        self.assertEqual(ctx.exception.code, "BUSINESS_CONFLICT")
        self.assertGreater(ctx.exception.details["album_refs"], 0)

    def test_conflict_does_not_delete_the_model(self):
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a2', 'A2', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.commit()
        try:
            self.service.delete(1)
        except svc.ServiceConflict:
            pass
        self.assertIsNotNone(
            self.conn.execute("SELECT id FROM model WHERE id = 1").fetchone()
        )


class TestModelServiceUpdateFields(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Old Name', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.log_calls = []
        self.service = svc.ModelService(
            db_factory=_db_factory(self.conn),
            log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_update_fields_returns_updated_dict(self):
        result = self.service.update_fields(1, {"display_name": "New Name"})
        self.assertIsInstance(result, dict)
        self.assertEqual(result["display_name"], "New Name")

    def test_update_fields_persists_changes(self):
        self.service.update_fields(1, {"display_name": "Persisted"})
        row = self.conn.execute(
            "SELECT display_name FROM model WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "Persisted")

    def test_update_fields_writes_audit_log(self):
        self.service.update_fields(1, {"display_name": "Logged"})
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertEqual(entry["action"], "update_model")
        self.assertEqual(entry["model_id"], 1)
        self.assertTrue(entry["success"])

    def test_update_fields_raises_not_found_for_missing_id(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.update_fields(999, {"display_name": "Ghost"})


# ---------------------------------------------------------------------------
# StudioService
# ---------------------------------------------------------------------------

class TestStudioServiceDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name) VALUES ('s1', 'MetArt')"
        )
        self.conn.commit()
        self.service = svc.StudioService(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_studio_succeeds(self):
        self.service.delete(1)
        self.assertIsNone(
            self.conn.execute("SELECT id FROM studio WHERE id = 1").fetchone()
        )

    def test_delete_raises_conflict_when_album_references_studio(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'A', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.delete(1)
        self.assertEqual(ctx.exception.code, "BUSINESS_CONFLICT")
        self.assertGreater(ctx.exception.details["album_refs"], 0)


# ---------------------------------------------------------------------------
# AlbumService
# ---------------------------------------------------------------------------

class TestAlbumServiceCreate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.log_calls = []
        self.service = svc.AlbumService(
            db_factory=_db_factory(self.conn),
            log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_create_returns_integer_id(self):
        album_id = self.service.create({"title": "Summer", "path": "/p"}, [], [])
        self.assertIsInstance(album_id, int)
        self.assertGreater(album_id, 0)

    def test_create_persists_album(self):
        self.service.create({"title": "Summer", "path": "/p"}, [], [])
        row = self.conn.execute(
            "SELECT title FROM album WHERE title = 'Summer'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_create_with_models_inserts_album_model(self):
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        album_id = self.service.create(
            {"title": "T"},
            [{"model_id": 1, "age_when_shot": 25, "role": "lead", "remarks": ""}],
            [],
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = ?", (album_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_create_with_relations_inserts_album_relation(self):
        # Create two albums, relate second to first.
        self.service.create({"title": "A1"}, [], [])
        album2_id = self.service.create(
            {"title": "A2"},
            [],
            [{"related_album_id": 1, "relation_type": "sequel", "remarks": ""}],
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_relation WHERE album_id = ?", (album2_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_create_writes_audit_log(self):
        self.service.create({"title": "Logged"}, [], [])
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertEqual(entry["action"], "create_album")
        self.assertTrue(entry["success"])


class TestAlbumServiceUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'Original', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.log_calls = []
        self.service = svc.AlbumService(
            db_factory=_db_factory(self.conn),
            log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_update_changes_album_title(self):
        self.service.update(1, {"title": "Updated"}, [], [])
        row = self.conn.execute("SELECT title FROM album WHERE id = 1").fetchone()
        self.assertEqual(row[0], "Updated")

    def test_update_replaces_model_list(self):
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.commit()
        self.service.update(1, {"title": "T"}, [], [])
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_update_replaces_relation_list(self):
        self.conn.execute(
            "INSERT INTO album_relation (album_id, related_album_id, relation_type)"
            " VALUES (1, 1, 'related')"
        )
        self.conn.commit()
        self.service.update(1, {"title": "T"}, [], [])
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_relation WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_update_writes_audit_log(self):
        self.service.update(1, {"title": "Logged"}, [], [])
        self.assertEqual(len(self.log_calls), 1)
        self.assertEqual(self.log_calls[0]["action"], "update_album")
        self.assertTrue(self.log_calls[0]["success"])


class TestAlbumServiceDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'ToDelete', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.execute(
            "INSERT INTO photo (uuid, album_id, filename, created_at)"
            " VALUES ('p1', 1, 'img.jpg', '2024-01-01')"
        )
        self.conn.commit()
        self.log_calls = []
        self.service = svc.AlbumService(
            db_factory=_db_factory(self.conn),
            log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_delete_removes_album(self):
        self.service.delete(1)
        self.assertIsNone(
            self.conn.execute("SELECT id FROM album WHERE id = 1").fetchone()
        )

    def test_delete_cascades_to_album_model(self):
        self.service.delete(1)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_delete_cascades_to_photos(self):
        self.service.delete(1)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM photo WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_delete_writes_audit_log(self):
        self.service.delete(1)
        self.assertEqual(len(self.log_calls), 1)
        self.assertEqual(self.log_calls[0]["action"], "delete_album")
        self.assertTrue(self.log_calls[0]["success"])


# ---------------------------------------------------------------------------
# WorkspaceAlbumService
# ---------------------------------------------------------------------------

class TestWorkspaceAlbumServiceBatchUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name) VALUES ('S', 'A')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name) VALUES ('S', 'B')"
        )
        self.conn.commit()
        self.snapshot_calls = []
        self.log_calls = []
        self.service = svc.WorkspaceAlbumService(
            db_factory=_db_factory(self.conn),
            snapshot_fn=lambda r, t="": self.snapshot_calls.append((r, t)) or MagicMock(name="snap.db"),
            backup_log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_batch_update_returns_updated_count(self):
        count = self.service.batch_update([1, 2], {"remark": "tagged"})
        self.assertEqual(count, 2)

    def test_batch_update_applies_changes(self):
        self.service.batch_update([1], {"remark": "new remark"})
        row = self.conn.execute(
            "SELECT remark FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "new remark")

    def test_batch_update_filters_disallowed_fields(self):
        self.service.batch_update([1], {"remark": "ok", "injected_col": "evil"})
        # Should not raise and 'injected_col' must be silently dropped
        row = self.conn.execute("SELECT remark FROM workspace_album WHERE id = 1").fetchone()
        self.assertEqual(row[0], "ok")

    def test_batch_update_raises_value_error_when_no_valid_fields(self):
        with self.assertRaises(ValueError):
            self.service.batch_update([1], {"injected_col": "evil"})

    def test_batch_update_takes_pre_write_snapshot(self):
        self.service.batch_update([1], {"remark": "snap-test"})
        self.assertTrue(
            any("workspace_batch" in str(c) for c in self.snapshot_calls),
            "Expected a snapshot labelled 'workspace_batch'",
        )

    def test_allowed_batch_fields_is_documented(self):
        """All allowed fields are present in the service's public constant."""
        expected = {
            "status_id", "studio_name", "album_name", "primary_model",
            "additional_models", "remark", "expected_path", "ai_result",
            "belongs_to_album_id", "album_id",
        }
        self.assertEqual(svc.WorkspaceAlbumService.ALLOWED_BATCH_FIELDS, expected)


class TestWorkspaceAlbumServiceUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, remark) VALUES ('S', 'old')"
        )
        self.conn.commit()
        self.service = svc.WorkspaceAlbumService(
            db_factory=_db_factory(self.conn),
            snapshot_fn=lambda *a, **kw: MagicMock(),
            backup_log_fn=lambda _: None,
        )

    def tearDown(self):
        self.conn.close()

    def test_update_applies_allowed_field(self):
        self.service.update(1, {"remark": "updated"})
        row = self.conn.execute(
            "SELECT remark FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "updated")

    def test_update_filters_disallowed_fields(self):
        self.service.update(1, {"remark": "good", "bad_col": "evil"})
        row = self.conn.execute(
            "SELECT remark FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "good")

    def test_update_raises_value_error_when_no_valid_fields(self):
        with self.assertRaises(ValueError):
            self.service.update(1, {"bad_col": "evil"})

    def test_allowed_update_fields_is_documented(self):
        expected = {
            "current_path", "expected_path", "primary_model", "studio_name",
            "album_name", "additional_models", "status_id", "remark",
            "belongs_to_album_id", "ai_result", "album_id",
        }
        self.assertEqual(svc.WorkspaceAlbumService.ALLOWED_UPDATE_FIELDS, expected)


# ---------------------------------------------------------------------------
# Import path helpers
# ---------------------------------------------------------------------------

class TestImportPathHelpers(unittest.TestCase):

    def test_parse_album_folder_name_with_pattern(self):
        model, album = svc.parse_album_folder_name("Alice in Wonderland")
        self.assertEqual(model, "Alice")
        self.assertEqual(album, "Wonderland")

    def test_parse_album_folder_name_case_insensitive(self):
        model, album = svc.parse_album_folder_name("Alice IN Wonderland")
        self.assertEqual(model, "Alice")

    def test_parse_album_folder_name_without_pattern(self):
        model, album = svc.parse_album_folder_name("PlainFolder")
        self.assertEqual(model, "")
        self.assertEqual(album, "PlainFolder")

    def test_alphabet_for_model_letter(self):
        self.assertEqual(svc.alphabet_for_model("Alice"), "A")

    def test_alphabet_for_model_digit(self):
        self.assertEqual(svc.alphabet_for_model("1Model"), "0-9")

    def test_alphabet_for_model_empty(self):
        self.assertEqual(svc.alphabet_for_model(""), "_")

    def test_build_archive_path_structure(self):
        path = svc.build_archive_path("Alice", "MetArt", "SummerShoot")
        self.assertEqual(path, "A/Alice/p/MetArt/SummerShoot")

    def test_build_archive_path_digit_model(self):
        path = svc.build_archive_path("1Top", "Studio", "Album")
        self.assertEqual(path, "0-9/1Top/p/Studio/Album")


# ---------------------------------------------------------------------------
# ImportService
# ---------------------------------------------------------------------------

class TestImportServicePreview(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name) VALUES ('s1', 'MetArt')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.service = svc.ImportService(
            db_factory=_db_factory(self.conn),
            snapshot_fn=lambda *a, **kw: MagicMock(),
            backup_log_fn=lambda _: None,
            change_log_fn=lambda _: None,
        )

    def tearDown(self):
        self.conn.close()

    def test_preview_returns_items_and_summary(self):
        result = self.service.preview([], archive_root="/archive", default_studio="MetArt")
        self.assertIn("items", result)
        self.assertIn("summary", result)

    def test_preview_parses_folder_name(self):
        items = [{"folder_name": "Alice in Shoot1"}]
        result = self.service.preview(items, "/archive", "MetArt")
        item = result["items"][0]
        self.assertEqual(item["model_name"], "Alice")
        self.assertEqual(item["album_name"], "Shoot1")

    def test_preview_detects_existing_studio(self):
        items = [{"model_name": "Alice", "album_name": "Shoot", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/archive", "MetArt")
        self.assertTrue(result["items"][0]["studio_exists"])

    def test_preview_detects_existing_model(self):
        items = [{"model_name": "Alice", "album_name": "S", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/archive", "MetArt")
        self.assertTrue(result["items"][0]["model_exists"])

    def test_preview_detects_existing_album(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Existing', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "Existing", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/archive", "MetArt")
        item = result["items"][0]
        self.assertTrue(item["album_exists"])
        self.assertFalse(item["can_import"])

    def test_preview_can_import_when_no_conflicts(self):
        items = [{"model_name": "Alice", "album_name": "NewShoot", "studio_name": "MetArt"}]
        # No album exists, path does not exist on disk (test environment)
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertTrue(result["items"][0]["can_import"])

    def test_preview_summary_counts(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Dup', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [
            {"model_name": "Alice", "album_name": "NewShoot", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Dup", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertEqual(result["summary"]["total"], 2)
        self.assertEqual(result["summary"]["importable"], 1)
        self.assertEqual(result["summary"]["skipped"], 1)


class TestImportServiceExecute(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.log_calls = []
        self.backup_calls = []
        self.snapshot_mock = MagicMock(name="snap.db")
        self.service = svc.ImportService(
            db_factory=_db_factory(self.conn),
            snapshot_fn=lambda *a, **kw: self.snapshot_mock,
            backup_log_fn=self.backup_calls.append,
            change_log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_execute_takes_pre_import_snapshot(self):
        self.service.execute([], "/archive", "MetArt")
        self.assertTrue(
            any(c.get("reason") == "import" for c in self.backup_calls),
            "Expected a backup log entry with reason='import'",
        )

    def test_execute_creates_studio_when_missing(self):
        items = [{"model_name": "Bob", "album_name": "Shoot", "studio_name": "NewStudio"}]
        self.service.execute(items, "/no-such-root", "NewStudio")
        row = self.conn.execute(
            "SELECT id FROM studio WHERE LOWER(name) = 'newstudio'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_execute_creates_model_when_missing(self):
        items = [{"model_name": "NewModel", "album_name": "Shoot", "studio_name": "S"}]
        self.service.execute(items, "/no-such-root", "S")
        row = self.conn.execute(
            "SELECT id FROM model WHERE LOWER(display_name) = 'newmodel'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_execute_reuses_existing_studio(self):
        self.conn.execute("INSERT INTO studio (uuid, name) VALUES ('s1', 'MetArt')")
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "Shoot", "studio_name": "MetArt"}]
        self.service.execute(items, "/no-such-root", "MetArt")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM studio WHERE LOWER(name) = 'metart'"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_execute_skips_existing_album(self):
        self.conn.execute("INSERT INTO studio (uuid, name) VALUES ('s1', 'S')")
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Dup', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "Dup", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertEqual(result["summary"]["skipped"], 1)
        self.assertEqual(result["summary"]["created"], 0)

    def test_execute_returns_summary_counts(self):
        items = [{"model_name": "Alice", "album_name": "Fresh", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["summary"]["created"], 1)
        self.assertEqual(result["summary"]["skipped"], 0)
        self.assertEqual(result["summary"]["errors"], 0)

    def test_execute_writes_change_log_for_created_album(self):
        items = [{"model_name": "Alice", "album_name": "Logged", "studio_name": "S"}]
        self.service.execute(items, "/no-such-root", "S")
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertEqual(entry["action"], "import_album")
        self.assertTrue(entry["success"])


# ---------------------------------------------------------------------------
# BackupService
# ---------------------------------------------------------------------------

class TestBackupServiceCreate(unittest.TestCase):

    def setUp(self):
        self.snap_path = MagicMock()
        self.snap_path.name = "Curator_20240101_120000_manual.db"
        self.snap_path.__str__ = lambda s: "/backups/Curator_20240101_120000_manual.db"
        self.log_calls = []
        self.service = svc.BackupService(
            snapshot_fn=lambda r, t="": self.snap_path,
            restore_fn=MagicMock(),
            backup_log_fn=self.log_calls.append,
            rollback_log_fn=lambda _: None,
            catalog_fn=lambda: [],
            last_change_fn=lambda: None,
            public_item_fn=lambda x: x,
            parse_tag_fn=lambda p: "",
        )

    def test_create_returns_snapshot_and_filename(self):
        result = self.service.create("manual", "")
        self.assertIn("snapshot", result)
        self.assertIn("filename", result)

    def test_create_logs_success(self):
        self.service.create("manual", "")
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertTrue(entry["ok"])
        self.assertEqual(entry["reason"], "manual")

    def test_create_logs_with_tag(self):
        self.service.create("manual", "my-tag")
        self.assertEqual(self.log_calls[0]["tag"], "my-tag")


class TestBackupServiceRollback(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.snap_file = Path(self.tmpdir) / "Curator_20240101_120000_manual.db"
        self.snap_file.write_bytes(b"")  # create the file

        self.catalog = [
            {
                "path": str(self.snap_file),
                "filename": self.snap_file.name,
                "tag": "",
                "created_at": "2024-01-01T12:00:00+00:00",
                "_created_at_dt": None,
            }
        ]
        self.restore_calls = []
        self.backup_log_calls = []
        self.rollback_log_calls = []

        self.service = svc.BackupService(
            snapshot_fn=lambda r, t="": self.snap_file,
            restore_fn=lambda p: self.restore_calls.append(p),
            backup_log_fn=self.backup_log_calls.append,
            rollback_log_fn=self.rollback_log_calls.append,
            catalog_fn=lambda: self.catalog,
            last_change_fn=lambda: None,
            public_item_fn=lambda x: x,
            parse_tag_fn=lambda p: "",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_rollback_snapshot_mode_calls_restore(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertEqual(len(self.restore_calls), 1)

    def test_rollback_snapshot_mode_creates_safety_snapshot(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertTrue(
            any(c.get("reason") == "pre_rollback" for c in self.backup_log_calls),
            "Expected a pre_rollback safety snapshot log entry",
        )

    def test_rollback_logs_success(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertTrue(
            any(c.get("ok") for c in self.rollback_log_calls),
            "Expected a successful rollback log entry",
        )

    def test_rollback_returns_selected_snapshot(self):
        result = self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertIn("selected_snapshot", result)

    def test_rollback_raises_value_error_for_unknown_mode(self):
        with self.assertRaises(ValueError):
            self.service.rollback("unknown_mode", {})

    def test_rollback_raises_value_error_when_snapshot_path_missing(self):
        with self.assertRaises(ValueError):
            self.service.rollback("snapshot", {})

    def test_rollback_raises_not_found_when_snapshot_file_absent(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.rollback("snapshot", {"snapshot": "/no/such/file.db"})

    def test_rollback_raises_value_error_when_tag_is_empty(self):
        with self.assertRaises(ValueError):
            self.service.rollback("tag", {"tag": ""})

    def test_rollback_raises_not_found_when_tag_not_in_catalog(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.rollback("tag", {"tag": "no-such-tag"})

    def test_rollback_before_last_operation_raises_not_found_when_no_log(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.rollback("before_last_operation", {})

    def test_rollback_tag_mode_finds_tagged_snapshot(self):
        tagged_file = Path(self.tmpdir) / "Curator_20240102_120000_manual_tag-my-tag.db"
        tagged_file.write_bytes(b"")
        self.catalog.append(
            {
                "path": str(tagged_file),
                "filename": tagged_file.name,
                "tag": "my-tag",
                "created_at": "2024-01-02T12:00:00+00:00",
                "_created_at_dt": None,
            }
        )
        result = self.service.rollback("tag", {"tag": "my-tag"})
        self.assertIn("selected_snapshot", result)
        self.assertEqual(self.restore_calls[-1], tagged_file)


if __name__ == "__main__":
    unittest.main()
