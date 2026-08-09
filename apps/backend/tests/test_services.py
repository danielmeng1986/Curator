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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call, patch

# Make the tools/web_ui package importable.
sys.path.insert(0, str(Path(__file__).parent.parent))

import repositories as repo
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
    album_id INTEGER,
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS repair_case (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    operation_uuid TEXT,
    album_uuid TEXT,
    expected_path TEXT,
    state TEXT NOT NULL DEFAULT 'NeedsRepair',
    category TEXT NOT NULL DEFAULT 'Assisted',
    confirmation TEXT,
    failure_reason TEXT,
    verification_result TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_operation TEXT,
    suggested_resolution TEXT,
    state TEXT NOT NULL DEFAULT 'Open',
    source_workflow TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    priority TEXT DEFAULT 'Normal',
    owner TEXT,
    due_date TEXT
);
CREATE TABLE IF NOT EXISTS operation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    initiator TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    summary TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    entity_uuid TEXT,
    import_uuid TEXT,
    batch_uuid TEXT,
    repair_uuid TEXT,
    related_operation_uuid TEXT,
    parent_operation_uuid TEXT,
    issue_uuid TEXT,
    error_category TEXT,
    error_code TEXT,
    error_details TEXT,
    repair_state TEXT,
    recovery_context TEXT
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
        status_repo = repo.StatusRepository(db_factory=_db_factory(self.conn))
        self.service = svc.StatusService(status_repo=status_repo)

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
        model_repo = repo.ModelRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ModelService(model_repo=model_repo)

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
        model_repo = repo.ModelRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ModelService(
            model_repo=model_repo,
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
        studio_repo = repo.StudioRepository(db_factory=_db_factory(self.conn))
        self.service = svc.StudioService(studio_repo=studio_repo)

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
        album_repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.AlbumService(
            album_repo=album_repo,
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

    def test_create_preserves_optional_permanent_remark(self):
        album_id = self.service.create({"title": "Summer", "remark": "curator note"}, [], [])
        row = self.conn.execute("SELECT remark FROM album WHERE id = ?", (album_id,)).fetchone()
        self.assertEqual("curator note", row[0])

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
        album_repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.AlbumService(
            album_repo=album_repo,
            log_fn=self.log_calls.append,
        )

    def tearDown(self):
        self.conn.close()

    def test_update_changes_album_title(self):
        self.service.update(1, {"title": "Updated"}, [], [])
        row = self.conn.execute("SELECT title FROM album WHERE id = 1").fetchone()
        self.assertEqual(row[0], "Updated")

    def test_update_preserves_optional_permanent_remark(self):
        self.service.update(1, {"title": "Updated", "remark": "reviewed"}, [], [])
        row = self.conn.execute("SELECT remark FROM album WHERE id = 1").fetchone()
        self.assertEqual("reviewed", row[0])

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
        album_repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.AlbumService(
            album_repo=album_repo,
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


class TestAlbumServiceReadiness(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, description, created_at, updated_at)"
            " VALUES ('a1', 'One', NULL, '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, description, created_at, updated_at)"
            " VALUES ('a2', 'Two', 'Existing', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.AlbumService(
            self.repo, lambda entry: None, preview_secret=b"test-preview-secret"
        )

    def tearDown(self):
        self.conn.close()

    def test_relationship_validation_rejects_missing_duplicate_and_self(self):
        with self.assertRaises(ValueError):
            self.service.update(1, {"title": "One"}, [{"model_id": 99}], [])
        with self.assertRaises(svc.ServiceConflict) as duplicate:
            self.service.update(1, {"title": "One"}, [{"model_id": 1}, {"model_id": 1}], [])
        self.assertEqual(duplicate.exception.code, "ALBUM_MODEL_DUPLICATE")
        with self.assertRaises(svc.ServiceConflict) as self_relation:
            self.service.update(1, {"title": "One"}, [], [{"related_album_id": 1}])
        self.assertEqual(self_relation.exception.code, "ALBUM_RELATION_SELF")

    def test_batch_preview_is_zero_write_and_blocks_unreviewed_overwrite(self):
        preview = self.service.preview_batch([1, 2], {"description": "Reviewed"})
        self.assertEqual(preview["summary"], {"total": 2, "eligible": 1, "blocked": 1})
        values = self.conn.execute("SELECT description FROM album ORDER BY id").fetchall()
        self.assertEqual([row[0] for row in values], [None, "Existing"])
        with self.assertRaises(svc.ServiceConflict) as blocked:
            self.service.execute_batch(preview["preview_token"])
        self.assertEqual(blocked.exception.code, "ALBUM_BATCH_OVERWRITE_NOT_REVIEWED")

    def test_reviewed_batch_executes_atomically(self):
        preview = self.service.preview_batch(
            [1, 2], {"description": "Reviewed"}, overwrite_non_empty=True
        )
        result = self.service.execute_batch(preview["preview_token"])
        self.assertEqual(result["summary"], {"total": 2, "succeeded": 2, "failed": 0})
        values = self.conn.execute("SELECT description FROM album ORDER BY id").fetchall()
        self.assertEqual([row[0] for row in values], ["Reviewed", "Reviewed"])

    def test_changed_album_rejects_batch_as_stale_without_partial_write(self):
        preview = self.service.preview_batch([1, 2], {"rating": 5})
        self.conn.execute("UPDATE album SET updated_at = '2025-01-01' WHERE id = 2")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as stale:
            self.service.execute_batch(preview["preview_token"])
        self.assertEqual(stale.exception.code, "ALBUM_BATCH_STALE")
        ratings = self.conn.execute("SELECT rating FROM album ORDER BY id").fetchall()
        self.assertEqual([row[0] for row in ratings], [None, None])


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
        workspace_repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.WorkspaceAlbumService(
            workspace_repo=workspace_repo,
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
        workspace_repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))
        self.service = svc.WorkspaceAlbumService(
            workspace_repo=workspace_repo,
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
        import_repo = repo.ImportRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=lambda *a, **kw: MagicMock(),
            backup_log_fn=lambda _: None,
            change_log_fn=lambda _: None,
            operation_service=svc.OperationService(
                repo.OperationRepository(_db_factory(self.conn))
            ),
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
        import_repo = repo.ImportRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=lambda *a, **kw: self.snapshot_mock,
            backup_log_fn=self.backup_calls.append,
            change_log_fn=self.log_calls.append,
            operation_service=svc.OperationService(
                repo.OperationRepository(_db_factory(self.conn))
            ),
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

    def test_execute_creates_succeeded_operation_linked_to_import_and_logs(self):
        result = self.service.execute(
            [{"model_name": "OperationModel", "album_name": "OperationAlbum", "studio_name": "S"}],
            "/no-such-root",
            "S",
            import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
        )

        operation = self.conn.execute(
            "SELECT * FROM operation WHERE import_uuid = ?", (result["import_uuid"],)
        ).fetchone()
        self.assertIsNotNone(operation)
        self.assertNotEqual(operation["uuid"], result["import_uuid"])
        self.assertEqual(operation["operation_type"], "import")
        self.assertEqual(operation["status"], svc.OP_STATUS_SUCCEEDED)
        self.assertEqual(self.log_calls[0]["operation_uuid"], operation["uuid"])
        self.assertEqual(self.backup_calls[0]["operation_uuid"], operation["uuid"])


# ---------------------------------------------------------------------------
# ImportService.execute — filesystem actions and NeedsRepair (BT-009)
# ---------------------------------------------------------------------------

class TestImportServiceExecuteActions(unittest.TestCase):
    """Filesystem Import Actions and failure-recovery recording."""

    def setUp(self):
        self.conn = _make_db()
        self.log_calls: list[dict] = []
        self.backup_calls: list[dict] = []
        import_repo = repo.ImportRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=lambda *a, **kw: MagicMock(),
            backup_log_fn=self.backup_calls.append,
            change_log_fn=self.log_calls.append,
            operation_service=svc.OperationService(
                repo.OperationRepository(_db_factory(self.conn))
            ),
        )

    def tearDown(self):
        self.conn.close()

    # --- import_uuid in result ---

    def test_execute_returns_import_uuid(self):
        result = self.service.execute([], "/archive", "S")
        self.assertIn("import_uuid", result)
        self.assertIsNotNone(result["import_uuid"])

    def test_import_uuid_differs_per_call(self):
        r1 = self.service.execute([], "/archive", "S")
        r2 = self.service.execute([], "/archive", "S")
        self.assertNotEqual(r1["import_uuid"], r2["import_uuid"])

    def test_import_uuid_in_change_log_entry(self):
        items = [{"model_name": "Alice", "album_name": "UuidTest", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertIn("import_uuid", self.log_calls[0])
        self.assertEqual(self.log_calls[0]["import_uuid"], result["import_uuid"])

    # --- Import Action constants ---

    def test_import_action_constants(self):
        self.assertEqual(svc.IMPORT_ACTION_DATABASE_ONLY, "DATABASE_ONLY")
        self.assertEqual(svc.IMPORT_ACTION_COPY, "COPY")
        self.assertEqual(svc.IMPORT_ACTION_MOVE, "MOVE")

    # --- Per-item result fields ---

    def test_result_item_has_needs_repair_key(self):
        items = [{"model_name": "Alice", "album_name": "FieldCheck", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertIn("needs_repair", result["results"][0])

    def test_result_item_has_effective_action_key(self):
        items = [{"model_name": "Alice", "album_name": "EffAction", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertIn("effective_action", result["results"][0])

    def test_summary_has_needs_repair_key(self):
        result = self.service.execute([], "/archive", "S")
        self.assertIn("needs_repair", result["summary"])

    def test_successful_item_needs_repair_is_false(self):
        items = [{"model_name": "Alice", "album_name": "Success", "studio_name": "S"}]
        result = self.service.execute(items, "/no-such-root", "S")
        self.assertFalse(result["results"][0]["needs_repair"])

    # --- DATABASE_ONLY action ---

    def test_database_only_action_creates_db_record(self):
        items = [{"model_name": "Alice", "album_name": "DbOnly", "studio_name": "S"}]
        self.service.execute(
            items, "/no-such-root", "S",
            import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
        )
        row = self.conn.execute(
            "SELECT id FROM album WHERE LOWER(title) = 'dbonly'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_database_only_action_does_not_touch_filesystem(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "source")
            os.makedirs(src_dir)
            items = [
                {"model_name": "Alice", "album_name": "DbOnly2", "studio_name": "S",
                 "source_path": src_dir}
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
            )
            # Destination should NOT be created by DATABASE_ONLY
            import canonical_path as cp
            expected = cp.build_canonical_path("Alice", "S", "DbOnly2")
            dest = os.path.join(tmpdir, expected)
            self.assertFalse(os.path.exists(dest))
        self.assertTrue(result["results"][0]["ok"])

    def test_database_only_effective_action_recorded(self):
        items = [{"model_name": "Alice", "album_name": "DbEffective", "studio_name": "S"}]
        result = self.service.execute(
            items, "/no-such-root", "S",
            import_action=svc.IMPORT_ACTION_DATABASE_ONLY,
        )
        self.assertEqual(result["results"][0]["effective_action"], "DATABASE_ONLY")

    # --- COPY action ---

    def test_copy_action_copies_source_to_dest(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "source_album")
            os.makedirs(src_dir)
            sentinel = os.path.join(src_dir, "photo.jpg")
            open(sentinel, "w").close()
            items = [
                {"model_name": "Alice", "album_name": "CopyShoot", "studio_name": "S",
                 "source_path": src_dir}
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_COPY,
            )
            import canonical_path as cp
            expected = cp.build_canonical_path("Alice", "S", "CopyShoot")
            dest_file = os.path.join(tmpdir, expected, "photo.jpg")
            self.assertTrue(os.path.isfile(dest_file))
            # Source still exists after copy
            self.assertTrue(os.path.exists(src_dir))
        self.assertTrue(result["results"][0]["ok"])

    def test_copy_effective_action_recorded_in_change_log(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            items = [
                {"model_name": "Alice", "album_name": "CopyLog", "studio_name": "S",
                 "source_path": src_dir}
            ]
            self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_COPY,
            )
        self.assertEqual(self.log_calls[0]["effective_action"], "COPY")

    # --- MOVE action ---

    def test_move_action_moves_source_to_dest(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "source_move")
            os.makedirs(src_dir)
            sentinel = os.path.join(src_dir, "photo.jpg")
            open(sentinel, "w").close()
            items = [
                {"model_name": "Alice", "album_name": "MoveShoot", "studio_name": "S",
                 "source_path": src_dir}
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
            import canonical_path as cp
            expected = cp.build_canonical_path("Alice", "S", "MoveShoot")
            dest_file = os.path.join(tmpdir, expected, "photo.jpg")
            self.assertTrue(os.path.isfile(dest_file))
            # Source is gone after move
            self.assertFalse(os.path.exists(src_dir))
        self.assertTrue(result["results"][0]["ok"])

    def test_move_effective_action_recorded_in_change_log(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src_move")
            os.makedirs(src_dir)
            items = [
                {"model_name": "Alice", "album_name": "MoveLog", "studio_name": "S",
                 "source_path": src_dir}
            ]
            self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        self.assertEqual(self.log_calls[0]["effective_action"], "MOVE")

    # --- Auto DATABASE_ONLY when source is already at destination ---

    def test_auto_database_only_when_source_at_destination(self):
        import tempfile, os
        import canonical_path as cp
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = cp.build_canonical_path("Alice", "S", "AtDest")
            dest_dir = os.path.join(tmpdir, expected)
            os.makedirs(dest_dir)
            source_file = os.path.join(dest_dir, "cover.jpg")
            Path(source_file).touch()
            items = [
                {"model_name": "Alice", "album_name": "AtDest", "studio_name": "S",
                 "source_path": dest_dir}   # source IS the destination
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
            self.assertTrue(os.path.isfile(source_file))
        item_result = result["results"][0]
        self.assertEqual(item_result["effective_action"], "DATABASE_ONLY")
        self.assertTrue(item_result["ok"])

    # --- NeedsRepair on filesystem failure after DB success ---

    def test_filesystem_failure_sets_needs_repair(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a non-existent source → shutil.move will raise
            items = [
                {"model_name": "Alice", "album_name": "RepairMe", "studio_name": "S",
                 "source_path": os.path.join(tmpdir, "nonexistent")}
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        item_result = result["results"][0]
        self.assertTrue(item_result["needs_repair"])
        self.assertFalse(item_result["ok"])
        self.assertIsNotNone(item_result["error"])
        operation = self.conn.execute(
            "SELECT * FROM operation WHERE import_uuid = ?", (result["import_uuid"],)
        ).fetchone()
        self.assertEqual(operation["status"], svc.OP_STATUS_NEEDS_REPAIR)
        self.assertEqual(operation["error_category"], "filesystem")
        self.assertEqual(operation["error_code"], "filesystem.write-failed")
        self.assertEqual(operation["repair_state"], "NeedsRepair")
        self.assertIn(result["import_uuid"], operation["recovery_context"])

    def test_persistence_failure_records_failed_operation(self):
        failing_repo = MagicMock()
        failing_repo.create_item.side_effect = sqlite3.OperationalError("database unavailable")
        service = svc.ImportService(
            import_repo=failing_repo,
            snapshot_fn=lambda *a, **kw: MagicMock(),
            backup_log_fn=lambda _: None,
            change_log_fn=lambda _: None,
            operation_service=svc.OperationService(
                repo.OperationRepository(_db_factory(self.conn))
            ),
        )

        result = service.execute(
            [{"model_name": "Broken", "album_name": "Write", "studio_name": "S"}],
            "/no-such-root",
            "S",
        )

        operation = self.conn.execute(
            "SELECT * FROM operation WHERE import_uuid = ?", (result["import_uuid"],)
        ).fetchone()
        self.assertEqual(result["summary"]["errors"], 1)
        self.assertEqual(operation["status"], svc.OP_STATUS_FAILED)
        self.assertEqual(operation["error_category"], "database")
        self.assertEqual(operation["error_code"], "database.transaction-failed")

    def test_filesystem_failure_db_record_still_exists(self):
        """DB record must persist even when the filesystem step fails."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            items = [
                {"model_name": "Alice", "album_name": "DbPersist", "studio_name": "S",
                 "source_path": os.path.join(tmpdir, "nonexistent")}
            ]
            self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        row = self.conn.execute(
            "SELECT id FROM album WHERE LOWER(title) = 'dbpersist'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_filesystem_failure_logs_needs_repair_in_change_log(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            items = [
                {"model_name": "Alice", "album_name": "LogRepair", "studio_name": "S",
                 "source_path": os.path.join(tmpdir, "nonexistent")}
            ]
            self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertTrue(entry["needs_repair"])
        self.assertFalse(entry["success"])

    def test_needs_repair_increments_summary_counter(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            items = [
                {"model_name": "Alice", "album_name": "CountRepair", "studio_name": "S",
                 "source_path": os.path.join(tmpdir, "nonexistent")}
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        self.assertEqual(result["summary"]["needs_repair"], 1)
        self.assertEqual(result["summary"]["errors"], 0)

    def test_mixed_success_and_needs_repair(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "good_source")
            os.makedirs(src_dir)
            items = [
                {"model_name": "Alice", "album_name": "GoodImport", "studio_name": "S",
                 "source_path": src_dir},
                {"model_name": "Alice", "album_name": "BadImport", "studio_name": "S",
                 "source_path": os.path.join(tmpdir, "nonexistent")},
            ]
            result = self.service.execute(
                items, tmpdir, "S",
                import_action=svc.IMPORT_ACTION_MOVE,
            )
        self.assertEqual(result["summary"]["created"], 1)
        self.assertEqual(result["summary"]["needs_repair"], 1)
        self.assertEqual(result["summary"]["errors"], 0)
        self.assertTrue(result["results"][0]["ok"])
        self.assertTrue(result["results"][1]["needs_repair"])


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

    def test_create_returns_safe_recovery_point_without_path(self):
        result = self.service.create("manual", "")
        self.assertEqual(result["recovery_point"]["filename"], self.snap_path.name)
        self.assertNotIn("snapshot", result)

    def test_create_logs_success(self):
        self.service.create("manual", "")
        self.assertEqual(len(self.log_calls), 1)
        entry = self.log_calls[0]
        self.assertTrue(entry["ok"])
        self.assertEqual(entry["reason"], "manual")

    def test_create_logs_with_tag(self):
        self.service.create("manual", "my-tag")
        self.assertEqual(self.log_calls[0]["tag"], "my-tag")


class TestAIWorkspaceContainerContract(unittest.TestCase):
    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.AIWorkspaceRepository(_db_factory(self.conn))
        self.service = svc.AIWorkspaceService(self.repo)

    def tearDown(self): self.conn.close()

    def test_open_close_archive_are_versioned_and_terminal(self):
        item = self.service.create("Album comparison")
        self.assertEqual("album_analysis", item["dataset_type"]); self.assertEqual("Open", item["lifecycle_state"])
        closed = self.service.close(item["uuid"], item["version"])
        self.assertEqual("Closed", closed["lifecycle_state"]); self.assertEqual(2, closed["version"])
        archived = self.service.archive(item["uuid"], closed["version"])
        self.assertEqual("Archived", archived["lifecycle_state"]); self.assertEqual(3, archived["version"])
        with self.assertRaises(svc.ServiceConflict): self.service.close(item["uuid"], archived["version"])

    def test_stale_transition_and_unknown_dataset_filter_are_rejected(self):
        item = self.service.create("Versioned")
        with self.assertRaisesRegex(svc.ServiceConflict, "changed"):
            self.service.close(item["uuid"], item["version"] + 1)
        with self.assertRaises(ValueError): self.service.list("active")

    def test_title_is_bounded(self):
        with self.assertRaises(ValueError): self.service.create("")
        with self.assertRaises(ValueError): self.service.create("x" * 201)


class TestBackupAdministrationContract(unittest.TestCase):
    class Claims:
        def __init__(self): self.claimed = set()
        def preview_is_claimed(self, value): return value in self.claimed
        def claim_preview(self, value, _at):
            if value in self.claimed: raise repo.PersistenceConflict({})
            self.claimed.add(value)

    def setUp(self):
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        self.raw = {"filename": "Curator_old_manual.db", "path": "/managed/Curator_old_manual.db",
                    "size_bytes": 12, "created_at": old, "reason": "manual", "tag": "before-change",
                    "protected": False, "retention_class": "ordinary", "_created_at_dt": None}
        self.deleted = []
        self.claims = self.Claims()
        self.service = svc.BackupService(
            snapshot_fn=MagicMock(), restore_fn=MagicMock(), backup_log_fn=MagicMock(),
            rollback_log_fn=MagicMock(), catalog_fn=lambda: [self.raw], last_change_fn=lambda: None,
            public_item_fn=lambda x: x, parse_tag_fn=lambda p: "", preview_secret=b"test-secret",
            cleanup_repo=self.claims, delete_snapshot_fn=lambda x: self.deleted.append(x["filename"]),
            verify_snapshot_fn=lambda x: {"verification_state": "verified"},
        )

    def test_catalog_omits_absolute_path_and_exposes_policy(self):
        item = self.service.recovery_points()[0]
        self.assertNotIn("path", item)
        self.assertTrue(item["cleanup_eligible"])
        self.assertEqual(item["protection_state"], "unprotected")

    def test_cleanup_requires_signed_review_and_is_single_use(self):
        preview = self.service.preview_cleanup()
        result = self.service.execute_cleanup(preview["preview_token"])
        self.assertEqual(result["deleted"][0]["filename"], self.raw["filename"])
        with self.assertRaisesRegex(svc.ServiceConflict, "already used"):
            self.service.execute_cleanup(preview["preview_token"])

    def test_tampered_cleanup_has_zero_effect(self):
        token = self.service.preview_cleanup()["preview_token"]
        with self.assertRaises(svc.ServiceConflict): self.service.execute_cleanup(token + "x")
        self.assertEqual(self.deleted, [])

    def test_protected_item_is_never_reviewed_for_cleanup(self):
        self.raw["protected"] = True
        preview = self.service.preview_cleanup()
        self.assertEqual(preview["summary"]["eligible"], 0)

    def test_verification_is_identity_bound(self):
        identity = self.service.recovery_points()[0]["identity"]
        self.assertEqual(self.service.verify(identity)["verification_state"], "verified")
        with self.assertRaises(svc.ServiceNotFound): self.service.verify("unknown")


class TestProtectedDatabaseRestoreContract(unittest.TestCase):
    class Claims:
        def __init__(self): self.values = set()
        def preview_is_claimed(self, value): return value in self.values
        def claim_preview(self, value, _at):
            if value in self.values: raise repo.PersistenceConflict({})
            self.values.add(value)

    def setUp(self):
        self.catalog = [{"filename": "Curator_target.db", "path": "/managed/Curator_target.db",
                         "size_bytes": 20, "created_at": "2024-01-01T00:00:00+00:00",
                         "reason": "manual", "tag": "target", "verification_state": "verified"}]
        self.claims = self.Claims(); self.snapshots = []; self.restores = []; self.state = "state-one"
        def snapshot(reason, tag):
            path = Path("/managed/Curator_safety.db"); self.snapshots.append(reason)
            self.catalog.append({"filename": path.name, "path": str(path), "size_bytes": 21,
                                 "created_at": datetime.now(timezone.utc).isoformat(),
                                 "reason": reason, "tag": tag, "verification_state": "not_verified"})
            return path
        def restore(path):
            self.restores.append(path); self.claims.values.clear(); self.state = "restored"
        def db_state(verify=False): return {"verified": True} if verify else self.state
        self.service = svc.BackupService(
            snapshot_fn=snapshot, restore_fn=restore, backup_log_fn=MagicMock(), rollback_log_fn=MagicMock(),
            catalog_fn=lambda: self.catalog, last_change_fn=lambda: None, public_item_fn=lambda x: x,
            parse_tag_fn=lambda p: "", preview_secret=b"restore-secret", restore_preview_repo=self.claims,
            database_state_fn=db_state, verify_snapshot_fn=lambda x: {"verification_state": "verified"},
        )
        self.identity = self.service.recovery_points()[0]["identity"]

    def test_unverified_target_cannot_be_previewed(self):
        self.catalog[0]["verification_state"] = "not_verified"
        with self.assertRaisesRegex(svc.ServiceConflict, "Verify"):
            self.service.preview_restore(self.identity)

    def test_confirmation_mismatch_has_zero_restore_effect(self):
        preview = self.service.preview_restore(self.identity)
        with self.assertRaises(svc.ServiceConflict):
            self.service.execute_restore(preview["preview_token"], "RESTORE something-else")
        self.assertEqual(self.snapshots, []); self.assertEqual(self.restores, [])

    def test_stale_database_has_zero_restore_effect(self):
        preview = self.service.preview_restore(self.identity); self.state = "state-two"
        with self.assertRaisesRegex(svc.ServiceConflict, "changed"):
            self.service.execute_restore(preview["preview_token"], preview["confirmation_phrase"])
        self.assertEqual(self.restores, [])

    def test_success_requires_safety_snapshot_and_reauthentication(self):
        preview = self.service.preview_restore(self.identity)
        result = self.service.execute_restore(preview["preview_token"], preview["confirmation_phrase"])
        self.assertEqual(self.snapshots, ["pre_restore_safety"])
        self.assertEqual(self.restores, [Path("/managed/Curator_target.db")])
        self.assertTrue(result["database_verified"]); self.assertTrue(result["reauthentication_required"])
        with self.assertRaisesRegex(svc.ServiceConflict, "already used"):
            self.service.execute_restore(preview["preview_token"], preview["confirmation_phrase"])

    def test_disposable_sqlite_restore_preserves_pre_restore_safety_copy(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root); active, target, safety = root / "active.db", root / "target.db", root / "safety.db"
            for path, value in ((active, "current"), (target, "target")):
                with sqlite3.connect(path) as conn:
                    conn.execute("CREATE TABLE marker (value TEXT)"); conn.execute("INSERT INTO marker VALUES (?)", (value,))
            catalog = [{"filename": target.name, "path": str(target), "size_bytes": target.stat().st_size,
                        "created_at": "2024-01-01T00:00:00+00:00", "verification_state": "verified"}]
            claims = self.Claims()
            def copy_db(source, destination):
                with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst: src.backup(dst)
            def snapshot(_reason, _tag):
                copy_db(active, safety); catalog.append({"filename": safety.name, "path": str(safety),
                    "size_bytes": safety.stat().st_size, "created_at": datetime.now(timezone.utc).isoformat()}); return safety
            def restore(path): copy_db(path, active); claims.values.clear()
            def state(verify=False):
                with sqlite3.connect(active) as conn:
                    if verify: return {"verified": conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"}
                    return conn.execute("SELECT value FROM marker").fetchone()[0]
            service = svc.BackupService(snapshot, restore, MagicMock(), MagicMock(), lambda: catalog,
                lambda: None, lambda x: x, lambda p: "", preview_secret=b"actual-restore",
                restore_preview_repo=claims, database_state_fn=state,
                verify_snapshot_fn=lambda item: {"verification_state": "verified"})
            identity = service.recovery_points()[0]["identity"]; preview = service.preview_restore(identity)
            service.execute_restore(preview["preview_token"], preview["confirmation_phrase"])
            with sqlite3.connect(active) as conn: self.assertEqual(conn.execute("SELECT value FROM marker").fetchone()[0], "target")
            with sqlite3.connect(safety) as conn: self.assertEqual(conn.execute("SELECT value FROM marker").fetchone()[0], "current")


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


# ---------------------------------------------------------------------------
# Snapshot policy functions (BT-011)
# ---------------------------------------------------------------------------

class TestAssessOperationRisk(unittest.TestCase):
    """Module-level assess_operation_risk() pure function."""

    # --- always-high-risk operations ---

    def test_data_migration_always_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(svc.SNAP_OP_DATA_MIGRATION)
        self.assertTrue(required)

    def test_data_migration_returns_high_risk_class(self):
        _, cls = svc.assess_operation_risk(svc.SNAP_OP_DATA_MIGRATION)
        self.assertEqual(cls, svc.SNAP_RETENTION_HIGH_RISK)

    def test_restore_always_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(svc.SNAP_OP_RESTORE)
        self.assertTrue(required)

    def test_restore_returns_high_risk_class(self):
        _, cls = svc.assess_operation_risk(svc.SNAP_OP_RESTORE)
        self.assertEqual(cls, svc.SNAP_RETENTION_HIGH_RISK)

    def test_always_high_risk_independent_of_item_count(self):
        # Even with zero items, always-high-risk operations require a snapshot.
        required, _ = svc.assess_operation_risk(svc.SNAP_OP_DATA_MIGRATION, item_count=0)
        self.assertTrue(required)

    # --- conditionally-high-risk: above threshold ---

    def test_bulk_import_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_IMPORT, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertTrue(required)

    def test_bulk_import_above_threshold_returns_high_risk_class(self):
        _, cls = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_IMPORT, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertEqual(cls, svc.SNAP_RETENTION_HIGH_RISK)

    def test_bulk_delete_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_DELETE, item_count=svc.SNAP_BULK_THRESHOLD + 1
        )
        self.assertTrue(required)

    def test_bulk_rename_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_RENAME, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertTrue(required)

    def test_bulk_quarantine_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_QUARANTINE, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertTrue(required)

    def test_workspace_promotion_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_WORKSPACE_PROMOTION, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertTrue(required)

    def test_relationship_rebuild_above_threshold_requires_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_RELATIONSHIP_REBUILD, item_count=svc.SNAP_BULK_THRESHOLD
        )
        self.assertTrue(required)

    # --- conditionally-high-risk: below threshold ---

    def test_bulk_import_below_threshold_no_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_IMPORT, item_count=svc.SNAP_BULK_THRESHOLD - 1
        )
        self.assertFalse(required)

    def test_bulk_import_below_threshold_returns_ordinary_class(self):
        _, cls = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_IMPORT, item_count=0
        )
        self.assertEqual(cls, svc.SNAP_RETENTION_ORDINARY)

    def test_bulk_delete_below_threshold_no_snapshot(self):
        required, _ = svc.assess_operation_risk(
            svc.SNAP_OP_BULK_DELETE, item_count=0
        )
        self.assertFalse(required)

    # --- ordinary operations ---

    def test_unknown_operation_type_no_snapshot(self):
        required, _ = svc.assess_operation_risk("crud_update")
        self.assertFalse(required)

    def test_unknown_operation_type_returns_ordinary_class(self):
        _, cls = svc.assess_operation_risk("crud_update")
        self.assertEqual(cls, svc.SNAP_RETENTION_ORDINARY)

    def test_empty_string_operation_type_no_snapshot(self):
        required, _ = svc.assess_operation_risk("")
        self.assertFalse(required)

    # --- BackupService.assess() wrapper ---

    def test_service_assess_snapshot_required_key(self):
        svc_obj = _minimal_backup_service()
        result = svc_obj.assess(svc.SNAP_OP_DATA_MIGRATION)
        self.assertIn("snapshot_required", result)
        self.assertTrue(result["snapshot_required"])

    def test_service_assess_retention_class_key(self):
        svc_obj = _minimal_backup_service()
        result = svc_obj.assess(svc.SNAP_OP_DATA_MIGRATION)
        self.assertIn("retention_class", result)
        self.assertEqual(result["retention_class"], svc.SNAP_RETENTION_HIGH_RISK)

    def test_service_assess_below_threshold_not_required(self):
        svc_obj = _minimal_backup_service()
        result = svc_obj.assess(svc.SNAP_OP_BULK_IMPORT, item_count=0)
        self.assertFalse(result["snapshot_required"])


def _minimal_backup_service():
    """Return a BackupService with no-op callables for all dependencies."""
    snap_path = MagicMock()
    snap_path.name = "Curator_test.db"
    snap_path.__str__ = lambda s: "/tmp/Curator_test.db"
    return svc.BackupService(
        snapshot_fn=lambda r, t="": snap_path,
        restore_fn=MagicMock(),
        backup_log_fn=lambda _: None,
        rollback_log_fn=lambda _: None,
        catalog_fn=lambda: [],
        last_change_fn=lambda: None,
        public_item_fn=lambda x: x,
        parse_tag_fn=lambda p: "",
    )


class TestIsRetentionEligible(unittest.TestCase):
    """Module-level is_retention_eligible() pure function."""

    def _record(self, *, created_at, retention_class="ordinary", protection_state="unprotected"):
        return {
            "created_at": created_at,
            "retention_class": retention_class,
            "protection_state": protection_state,
        }

    def _now(self):
        from datetime import timezone
        return datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    # --- ordinary retention (30 days) ---

    def test_ordinary_exactly_30_days_is_eligible(self):
        from datetime import timedelta, timezone
        created = datetime(2024, 5, 2, 0, 0, 0, tzinfo=timezone.utc)  # 30 days before now
        record = self._record(created_at=created.isoformat())
        self.assertTrue(svc.is_retention_eligible(record, now=self._now()))

    def test_ordinary_29_days_is_not_eligible(self):
        from datetime import timedelta, timezone
        created = datetime(2024, 5, 3, 0, 0, 0, tzinfo=timezone.utc)  # 29 days before now
        record = self._record(created_at=created.isoformat())
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    def test_ordinary_60_days_is_eligible(self):
        from datetime import timezone
        created = datetime(2024, 4, 1, 0, 0, 0, tzinfo=timezone.utc)  # 61 days before now
        record = self._record(created_at=created.isoformat())
        self.assertTrue(svc.is_retention_eligible(record, now=self._now()))

    # --- high-risk retention (180 days) ---

    def test_high_risk_exactly_180_days_is_eligible(self):
        from datetime import timezone
        created = datetime(2023, 12, 4, 0, 0, 0, tzinfo=timezone.utc)  # 179 days before Jun 1 2024
        # Adjust: 180 days before Jun 1 2024 = Dec 4 2023
        created = datetime(2023, 12, 4, 0, 0, 0, tzinfo=timezone.utc)
        # Jun 1 - 180 days = Dec 4, so that should be exactly 179 days. Let me use
        # a precise computation.
        from datetime import timedelta
        created = self._now() - timedelta(days=180)
        record = self._record(
            created_at=created.isoformat(),
            retention_class=svc.SNAP_RETENTION_HIGH_RISK,
        )
        self.assertTrue(svc.is_retention_eligible(record, now=self._now()))

    def test_high_risk_179_days_is_not_eligible(self):
        from datetime import timedelta
        created = self._now() - timedelta(days=179)
        record = self._record(
            created_at=created.isoformat(),
            retention_class=svc.SNAP_RETENTION_HIGH_RISK,
        )
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    def test_high_risk_200_days_is_eligible(self):
        from datetime import timedelta
        created = self._now() - timedelta(days=200)
        record = self._record(
            created_at=created.isoformat(),
            retention_class=svc.SNAP_RETENTION_HIGH_RISK,
        )
        self.assertTrue(svc.is_retention_eligible(record, now=self._now()))

    # --- protected snapshots (never eligible) ---

    def test_protected_ordinary_expired_is_not_eligible(self):
        from datetime import timedelta
        created = self._now() - timedelta(days=60)
        record = self._record(
            created_at=created.isoformat(),
            protection_state=svc.SNAP_PROTECTION_PROTECTED,
        )
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    def test_protected_high_risk_expired_is_not_eligible(self):
        from datetime import timedelta
        created = self._now() - timedelta(days=200)
        record = self._record(
            created_at=created.isoformat(),
            retention_class=svc.SNAP_RETENTION_HIGH_RISK,
            protection_state=svc.SNAP_PROTECTION_PROTECTED,
        )
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    # --- missing / invalid data ---

    def test_no_created_at_is_not_eligible(self):
        record = self._record(created_at=None)
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    def test_invalid_created_at_is_not_eligible(self):
        record = self._record(created_at="not-a-date")
        self.assertFalse(svc.is_retention_eligible(record, now=self._now()))

    def test_missing_retention_class_defaults_to_ordinary(self):
        from datetime import timedelta
        created = self._now() - timedelta(days=60)
        record = {"created_at": created.isoformat()}
        self.assertTrue(svc.is_retention_eligible(record, now=self._now()))


class TestBackupServicePurgeEligible(unittest.TestCase):
    """BackupService.purge_eligible() applies the retention hard gate."""

    def setUp(self):
        self.service = _minimal_backup_service()
        from datetime import timedelta, timezone
        self.now = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.old_ordinary = {
            "path": "/snaps/old.db",
            "created_at": (self.now - timedelta(days=60)).isoformat(),
            "retention_class": svc.SNAP_RETENTION_ORDINARY,
            "protection_state": svc.SNAP_PROTECTION_NONE,
        }
        self.fresh_ordinary = {
            "path": "/snaps/fresh.db",
            "created_at": (self.now - timedelta(days=10)).isoformat(),
            "retention_class": svc.SNAP_RETENTION_ORDINARY,
            "protection_state": svc.SNAP_PROTECTION_NONE,
        }
        self.old_high_risk = {
            "path": "/snaps/old_hr.db",
            "created_at": (self.now - timedelta(days=200)).isoformat(),
            "retention_class": svc.SNAP_RETENTION_HIGH_RISK,
            "protection_state": svc.SNAP_PROTECTION_NONE,
        }
        self.recent_high_risk = {
            "path": "/snaps/recent_hr.db",
            "created_at": (self.now - timedelta(days=100)).isoformat(),
            "retention_class": svc.SNAP_RETENTION_HIGH_RISK,
            "protection_state": svc.SNAP_PROTECTION_NONE,
        }
        self.protected_old = {
            "path": "/snaps/protected.db",
            "created_at": (self.now - timedelta(days=400)).isoformat(),
            "retention_class": svc.SNAP_RETENTION_ORDINARY,
            "protection_state": svc.SNAP_PROTECTION_PROTECTED,
        }

    def test_empty_catalog_returns_empty(self):
        result = self.service.purge_eligible([], now=self.now)
        self.assertEqual(result, [])

    def test_expired_ordinary_is_eligible(self):
        result = self.service.purge_eligible([self.old_ordinary], now=self.now)
        self.assertIn(self.old_ordinary, result)

    def test_fresh_ordinary_is_not_eligible(self):
        result = self.service.purge_eligible([self.fresh_ordinary], now=self.now)
        self.assertNotIn(self.fresh_ordinary, result)

    def test_expired_high_risk_is_eligible(self):
        result = self.service.purge_eligible([self.old_high_risk], now=self.now)
        self.assertIn(self.old_high_risk, result)

    def test_recent_high_risk_is_not_eligible(self):
        result = self.service.purge_eligible([self.recent_high_risk], now=self.now)
        self.assertNotIn(self.recent_high_risk, result)

    def test_protected_expired_is_not_eligible(self):
        result = self.service.purge_eligible([self.protected_old], now=self.now)
        self.assertNotIn(self.protected_old, result)

    def test_mixed_catalog_only_returns_eligible(self):
        catalog = [
            self.old_ordinary,    # eligible
            self.fresh_ordinary,  # not eligible
            self.old_high_risk,   # eligible
            self.recent_high_risk,# not eligible
            self.protected_old,   # not eligible (protected)
        ]
        result = self.service.purge_eligible(catalog, now=self.now)
        self.assertCountEqual(result, [self.old_ordinary, self.old_high_risk])

    def test_all_protected_returns_empty(self):
        catalog = [
            {**self.old_ordinary, "protection_state": svc.SNAP_PROTECTION_PROTECTED},
            {**self.old_high_risk, "protection_state": svc.SNAP_PROTECTION_PROTECTED},
        ]
        result = self.service.purge_eligible(catalog, now=self.now)
        self.assertEqual(result, [])


class TestBackupServiceRestoreSuccess(unittest.TestCase):
    """BackupService.rollback() restore success and safety snapshot behavior."""

    def setUp(self):
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        self.snap_file = self.tmpdir / "Curator_20240101_120000.db"
        self.snap_file.write_bytes(b"")

        self.restore_calls = []
        self.backup_log_calls = []
        self.rollback_log_calls = []
        safety_snap = self.tmpdir / "Curator_pre_rollback.db"
        safety_snap.write_bytes(b"")

        self.service = svc.BackupService(
            snapshot_fn=lambda r, t="": safety_snap,
            restore_fn=lambda p: self.restore_calls.append(p),
            backup_log_fn=self.backup_log_calls.append,
            rollback_log_fn=self.rollback_log_calls.append,
            catalog_fn=lambda: [],
            last_change_fn=lambda: None,
            public_item_fn=lambda x: x,
            parse_tag_fn=lambda p: "",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_restore_calls_restore_fn(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertEqual(len(self.restore_calls), 1)
        self.assertEqual(self.restore_calls[0], self.snap_file)

    def test_restore_creates_safety_snapshot_before_restore(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        pre_rollback_entries = [
            c for c in self.backup_log_calls if c.get("reason") == "pre_rollback"
        ]
        self.assertGreater(len(pre_rollback_entries), 0)

    def test_restore_logs_success_outcome(self):
        self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        success_entries = [c for c in self.rollback_log_calls if c.get("ok")]
        self.assertGreater(len(success_entries), 0)

    def test_restore_returns_selected_snapshot_key(self):
        result = self.service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        self.assertIn("selected_snapshot", result)

    def test_restore_failure_logs_failure_outcome(self):
        def failing_restore(p):
            raise IOError("disk error")

        failing_service = svc.BackupService(
            snapshot_fn=lambda r, t="": self.snap_file,
            restore_fn=failing_restore,
            backup_log_fn=lambda _: None,
            rollback_log_fn=self.rollback_log_calls.append,
            catalog_fn=lambda: [],
            last_change_fn=lambda: None,
            public_item_fn=lambda x: x,
            parse_tag_fn=lambda p: "",
        )
        with self.assertRaises(IOError):
            failing_service.rollback("snapshot", {"snapshot": str(self.snap_file)})
        failure_entries = [c for c in self.rollback_log_calls if not c.get("ok")]
        self.assertGreater(len(failure_entries), 0)

def _make_workspace_service(conn):
    """Helper: build a WorkspaceAlbumService with snapshot/log no-ops."""
    workspace_repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(conn))
    return svc.WorkspaceAlbumService(
        workspace_repo=workspace_repo,
        snapshot_fn=lambda tag: None,
        backup_log_fn=lambda entry: None,
    )


class TestWorkspaceAlbumServiceCreate(unittest.TestCase):
    """Tests for WorkspaceAlbumService.create()."""

    def setUp(self):
        self.conn = _make_db()
        self.service = _make_workspace_service(self.conn)

    def test_create_returns_dict_with_id(self):
        result = self.service.create({"studio_name": "Studio A", "album_name": "Album 1"})
        self.assertIn("id", result)

    def test_create_sets_lifecycle_state_active(self):
        result = self.service.create({"studio_name": "Studio A"})
        self.assertEqual(result["lifecycle_state"], "active")

    def test_create_persists_fields(self):
        result = self.service.create(
            {"studio_name": "Studio B", "album_name": "Summer", "primary_model": "Alice"}
        )
        self.assertEqual(result["studio_name"], "Studio B")
        self.assertEqual(result["album_name"], "Summer")

    def test_create_ignores_lifecycle_state_from_caller(self):
        # lifecycle_state is not in ALLOWED_CREATE_FIELDS; must always be 'active'.
        result = self.service.create({"studio_name": "S", "lifecycle_state": "closed"})
        self.assertEqual(result["lifecycle_state"], "active")

    def test_allowed_create_fields_does_not_include_lifecycle_state(self):
        self.assertNotIn("lifecycle_state", svc.WorkspaceAlbumService.ALLOWED_CREATE_FIELDS)


class TestWorkspaceAlbumServiceLifecycleTransitions(unittest.TestCase):
    """Tests for lifecycle transition methods in WorkspaceAlbumService."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, lifecycle_state) VALUES ('S', 'active')"
        )
        self.conn.commit()
        self.service = _make_workspace_service(self.conn)

    def _state(self) -> str:
        return self.conn.execute(
            "SELECT lifecycle_state FROM workspace_album WHERE id = 1"
        ).fetchone()[0]

    # --- Valid transitions ---

    def test_submit_for_review_active_to_review(self):
        self.service.submit_for_review(1)
        self.assertEqual(self._state(), "review")

    def test_return_to_active_review_to_active(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='review' WHERE id=1")
        self.conn.commit()
        self.service.return_to_active(1)
        self.assertEqual(self._state(), "active")

    def test_close_review_to_closed(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='review' WHERE id=1")
        self.conn.commit()
        self.service.close(1)
        self.assertEqual(self._state(), "closed")

    def test_archive_closed_to_archived_retired(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='closed' WHERE id=1")
        self.conn.commit()
        self.service.archive(1)
        self.assertEqual(self._state(), "archived_retired")

    def test_full_happy_path(self):
        # active → review → closed → archived_retired
        self.service.submit_for_review(1)
        self.service.close(1)
        self.service.archive(1)
        self.assertEqual(self._state(), "archived_retired")

    def test_round_trip_active_review_active(self):
        self.service.submit_for_review(1)
        self.service.return_to_active(1)
        self.assertEqual(self._state(), "active")

    # --- Invalid transitions raise ServiceConflict ---

    def test_submit_for_review_from_review_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='review' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict) as ctx:
            self.service.submit_for_review(1)
        self.assertEqual(ctx.exception.code, "BUSINESS_CONFLICT")

    def test_submit_for_review_from_closed_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='closed' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.submit_for_review(1)

    def test_submit_for_review_from_archived_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='archived_retired' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.submit_for_review(1)

    def test_return_to_active_from_active_raises_conflict(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.return_to_active(1)

    def test_return_to_active_from_closed_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='closed' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.return_to_active(1)

    def test_close_from_active_raises_conflict(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.close(1)

    def test_close_from_closed_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='closed' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.close(1)

    def test_archive_from_active_raises_conflict(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.archive(1)

    def test_archive_from_review_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='review' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.archive(1)

    def test_archive_from_archived_raises_conflict(self):
        self.conn.execute("UPDATE workspace_album SET lifecycle_state='archived_retired' WHERE id=1")
        self.conn.commit()
        with self.assertRaises(svc.ServiceConflict):
            self.service.archive(1)

    # --- Invalid operations do not modify persisted state ---

    def test_invalid_transition_does_not_change_state(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.close(1)  # active → closed is invalid
        self.assertEqual(self._state(), "active")

    # --- Not-found raises ServiceNotFound ---

    def test_submit_for_review_missing_id_raises_not_found(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.submit_for_review(9999)

    def test_return_to_active_missing_id_raises_not_found(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.return_to_active(9999)

    def test_close_missing_id_raises_not_found(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.close(9999)

    def test_archive_missing_id_raises_not_found(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.archive(9999)

    # --- Lifecycle state constants are correct ---

    def test_lifecycle_constants_values(self):
        self.assertEqual(svc.LIFECYCLE_ACTIVE, "active")
        self.assertEqual(svc.LIFECYCLE_REVIEW, "review")
        self.assertEqual(svc.LIFECYCLE_CLOSED, "closed")
        self.assertEqual(svc.LIFECYCLE_ARCHIVED_RETIRED, "archived_retired")

    def test_allowed_update_fields_excludes_lifecycle_state(self):
        self.assertNotIn("lifecycle_state", svc.WorkspaceAlbumService.ALLOWED_UPDATE_FIELDS)

    def test_allowed_batch_fields_excludes_lifecycle_state(self):
        self.assertNotIn("lifecycle_state", svc.WorkspaceAlbumService.ALLOWED_BATCH_FIELDS)


# ---------------------------------------------------------------------------
# ImportService.preview — structured validation and collision detection (BT-008)
# ---------------------------------------------------------------------------

class TestImportServicePreviewValidation(unittest.TestCase):
    """Structured validation outcomes and collision detection in ImportService.preview()."""

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
        import_repo = repo.ImportRepository(db_factory=_db_factory(self.conn))
        self.service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=lambda *a, **kw: None,
            backup_log_fn=lambda _: None,
            change_log_fn=lambda _: None,
            operation_service=svc.OperationService(
                repo.OperationRepository(_db_factory(self.conn))
            ),
        )

    def tearDown(self):
        self.conn.close()

    # --- validation_errors field shape ---

    def test_preview_item_has_validation_errors_key(self):
        items = [{"model_name": "Alice", "album_name": "NewShoot", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertIn("validation_errors", result["items"][0])

    def test_validation_errors_is_empty_for_clean_import(self):
        items = [{"model_name": "Alice", "album_name": "CleanShoot", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertEqual(result["items"][0]["validation_errors"], [])

    def test_validation_errors_is_list(self):
        items = [{"model_name": "Alice", "album_name": "S", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertIsInstance(result["items"][0]["validation_errors"], list)

    def test_each_validation_error_has_code_and_message(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Existing', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "Existing", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        for err in result["items"][0]["validation_errors"]:
            self.assertIn("code", err)
            self.assertIn("message", err)

    # --- ALBUM_EXISTS ---

    def test_album_exists_adds_validation_error_code(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'DupAlbum', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "DupAlbum", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        codes = [e["code"] for e in result["items"][0]["validation_errors"]]
        self.assertIn("ALBUM_EXISTS", codes)

    def test_album_exists_sets_can_import_false(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'DupAlbum', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [{"model_name": "Alice", "album_name": "DupAlbum", "studio_name": "MetArt"}]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertFalse(result["items"][0]["can_import"])

    # --- PATH_EXISTS (filesystem collision) ---

    def test_path_exists_adds_validation_error_code(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            # Build the directory so full_path.exists() is True
            expected = "A/Alice/p/MetArt/PathExistShoot"
            os.makedirs(os.path.join(tmpdir, expected), exist_ok=True)
            items = [
                {"model_name": "Alice", "album_name": "PathExistShoot",
                 "studio_name": "MetArt"}
            ]
            result = self.service.preview(items, tmpdir, "MetArt")
        codes = [e["code"] for e in result["items"][0]["validation_errors"]]
        self.assertIn("PATH_EXISTS", codes)

    def test_path_exists_sets_can_import_false(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            expected = "A/Alice/p/MetArt/FsCollide"
            os.makedirs(os.path.join(tmpdir, expected), exist_ok=True)
            items = [
                {"model_name": "Alice", "album_name": "FsCollide",
                 "studio_name": "MetArt"}
            ]
            result = self.service.preview(items, tmpdir, "MetArt")
        self.assertFalse(result["items"][0]["can_import"])

    def test_source_already_at_canonical_destination_is_importable(self):
        import tempfile
        import canonical_path as cp

        with tempfile.TemporaryDirectory() as tmpdir:
            expected = cp.build_canonical_path("Alice", "MetArt", "AlreadyHome")
            source = Path(tmpdir) / expected
            source.mkdir(parents=True)
            items = [{
                "model_name": "Alice",
                "album_name": "AlreadyHome",
                "studio_name": "MetArt",
                "source_path": str(source),
            }]
            result = self.service.preview(items, tmpdir, "MetArt")

        item = result["items"][0]
        codes = [e["code"] for e in item["validation_errors"]]
        self.assertTrue(item["path_exists"])
        self.assertTrue(item["source_at_canonical_destination"])
        self.assertEqual(item["effective_action"], svc.IMPORT_ACTION_DATABASE_ONLY)
        self.assertNotIn("PATH_EXISTS", codes)
        self.assertTrue(item["can_import"])

    def test_existing_destination_different_from_source_remains_conflict(self):
        import tempfile
        import canonical_path as cp

        with tempfile.TemporaryDirectory() as tmpdir:
            expected = cp.build_canonical_path("Alice", "MetArt", "Occupied")
            destination = Path(tmpdir) / expected
            destination.mkdir(parents=True)
            source = Path(tmpdir) / "unmanaged-source"
            source.mkdir()
            items = [{
                "model_name": "Alice",
                "album_name": "Occupied",
                "studio_name": "MetArt",
                "source_path": str(source),
            }]
            result = self.service.preview(items, tmpdir, "MetArt")

        item = result["items"][0]
        codes = [e["code"] for e in item["validation_errors"]]
        self.assertFalse(item["source_at_canonical_destination"])
        self.assertIn("PATH_EXISTS", codes)
        self.assertFalse(item["can_import"])

    # --- DUPLICATE_IN_BATCH ---

    def test_duplicate_in_batch_flags_both_items(self):
        items = [
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        for item in result["items"]:
            codes = [e["code"] for e in item["validation_errors"]]
            self.assertIn("DUPLICATE_IN_BATCH", codes)

    def test_duplicate_in_batch_both_items_not_importable(self):
        items = [
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        for item in result["items"]:
            self.assertFalse(item["can_import"])

    def test_duplicate_in_batch_does_not_flag_unique_items(self):
        items = [
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Winter", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        for item in result["items"]:
            codes = [e["code"] for e in item["validation_errors"]]
            self.assertNotIn("DUPLICATE_IN_BATCH", codes)

    def test_duplicate_in_batch_case_insensitive(self):
        # "SUMMER" and "summer" normalize to same comparison key — both flagged
        items = [
            {"model_name": "Alice", "album_name": "SUMMER", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "summer", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        for item in result["items"]:
            codes = [e["code"] for e in item["validation_errors"]]
            self.assertIn("DUPLICATE_IN_BATCH", codes)

    def test_three_items_one_duplicate_one_clean(self):
        items = [
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"},
            {"model_name": "Alice", "album_name": "Winter", "studio_name": "MetArt"},
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        codes_0 = [e["code"] for e in result["items"][0]["validation_errors"]]
        codes_1 = [e["code"] for e in result["items"][1]["validation_errors"]]
        codes_2 = [e["code"] for e in result["items"][2]["validation_errors"]]
        self.assertIn("DUPLICATE_IN_BATCH", codes_0)
        self.assertIn("DUPLICATE_IN_BATCH", codes_1)
        self.assertNotIn("DUPLICATE_IN_BATCH", codes_2)
        self.assertTrue(result["items"][2]["can_import"])

    # --- PATH_COLLISION (DB canonical-path collision) ---

    def test_path_collision_adds_validation_error_code(self):
        # Store an album with a path that matches the proposed canonical path.
        import canonical_path as cp
        proposed = cp.build_canonical_path("Alice", "MetArt", "PathCollideShoot")
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, path, created_at, updated_at)"
            " VALUES ('a1', 1, 'OtherTitle', ?, '2024-01-01', '2024-01-01')",
            (proposed,),
        )
        self.conn.commit()
        items = [
            {"model_name": "Alice", "album_name": "PathCollideShoot",
             "studio_name": "MetArt"}
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        codes = [e["code"] for e in result["items"][0]["validation_errors"]]
        self.assertIn("PATH_COLLISION", codes)

    def test_path_collision_sets_can_import_false(self):
        import canonical_path as cp
        proposed = cp.build_canonical_path("Alice", "MetArt", "Collision2")
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, path, created_at, updated_at)"
            " VALUES ('a1', 1, 'OtherTitle2', ?, '2024-01-01', '2024-01-01')",
            (proposed,),
        )
        self.conn.commit()
        items = [
            {"model_name": "Alice", "album_name": "Collision2", "studio_name": "MetArt"}
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertFalse(result["items"][0]["can_import"])

    def test_no_path_collision_when_path_is_different(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, path, created_at, updated_at)"
            " VALUES ('a1', 1, 'Other', 'A/Alice/p/MetArt/Other', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        items = [
            {"model_name": "Alice", "album_name": "Unique", "studio_name": "MetArt"}
        ]
        result = self.service.preview(items, "/no-such-root", "MetArt")
        codes = [e["code"] for e in result["items"][0]["validation_errors"]]
        self.assertNotIn("PATH_COLLISION", codes)
        self.assertTrue(result["items"][0]["can_import"])

    # --- Determinism ---

    def test_preview_is_deterministic(self):
        items = [
            {"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"}
        ]
        r1 = self.service.preview(items, "/no-such-root", "MetArt")
        r2 = self.service.preview(items, "/no-such-root", "MetArt")
        self.assertEqual(r1["items"][0]["expected_path"], r2["items"][0]["expected_path"])
        self.assertEqual(
            r1["items"][0]["validation_errors"],
            r2["items"][0]["validation_errors"],
        )

    def test_normalized_input_equivalent_to_unnormalized(self):
        # Whitespace-padded and clean inputs must produce the same preview.
        items_clean = [{"model_name": "Alice", "album_name": "Summer", "studio_name": "MetArt"}]
        items_padded = [{"model_name": "  Alice  ", "album_name": " Summer ", "studio_name": " MetArt "}]
        r_clean = self.service.preview(items_clean, "/no-such-root", "MetArt")
        r_padded = self.service.preview(items_padded, "/no-such-root", "MetArt")
        self.assertEqual(
            r_clean["items"][0]["expected_path"],
            r_padded["items"][0]["expected_path"],
        )


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# RepairService — lifecycle and validation tests
# ---------------------------------------------------------------------------

class TestRepairServiceDetect(unittest.TestCase):
    """RepairService.detect() creates a repair case + linked Issue."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.repair_repo = repo.RepairRepository(factory)
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.RepairService(self.repair_repo, self.issue_repo)

    def test_detect_returns_repair_and_issue(self):
        result = self.service.detect("op-1", "album-1", "/path/to/album")
        self.assertIn("repair", result)
        self.assertIn("issue", result)

    def test_repair_state_is_needs_repair(self):
        result = self.service.detect("op-1", "album-1", "/path")
        self.assertEqual(result["repair"]["state"], "NeedsRepair")

    def test_issue_state_is_open(self):
        result = self.service.detect("op-1", "album-1", "/path")
        self.assertEqual(result["issue"]["state"], "Open")

    def test_repair_operation_uuid_stored(self):
        result = self.service.detect("op-xyz", "album-1", "/path")
        self.assertEqual(result["repair"]["operation_uuid"], "op-xyz")

    def test_repair_album_uuid_stored(self):
        result = self.service.detect("op-1", "alb-abc", "/path")
        self.assertEqual(result["repair"]["album_uuid"], "alb-abc")

    def test_repair_expected_path_stored(self):
        result = self.service.detect("op-1", "album-1", "/expected/path")
        self.assertEqual(result["repair"]["expected_path"], "/expected/path")

    def test_failure_reason_stored(self):
        result = self.service.detect(
            "op-1", "album-1", "/path", failure_reason="dir missing"
        )
        self.assertEqual(result["repair"]["failure_reason"], "dir missing")

    def test_default_category_is_assisted(self):
        result = self.service.detect("op-1", "album-1", "/path")
        self.assertEqual(result["repair"]["category"], "Assisted")

    def test_category_automatic_stored(self):
        result = self.service.detect(
            "op-1", "album-1", "/path", category="Automatic"
        )
        self.assertEqual(result["repair"]["category"], "Automatic")

    def test_issue_source_workflow_is_repair_service(self):
        result = self.service.detect("op-1", "album-1", "/path")
        self.assertEqual(result["issue"]["source_workflow"], "RepairService")

    def test_issue_category_is_repair(self):
        result = self.service.detect("op-1", "album-1", "/path")
        self.assertEqual(result["issue"]["category"], "Repair")


class TestRepairServiceLifecycleAutomatic(unittest.TestCase):
    """Automatic repairs require no confirmation."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.repair_repo = repo.RepairRepository(factory)
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.RepairService(self.repair_repo, self.issue_repo)
        result = self.service.detect(
            "op-1", "album-1", "/path", category="Automatic"
        )
        self.repair_uuid = result["repair"]["uuid"]

    def test_start_repair_without_confirmation(self):
        updated = self.service.start_repair(self.repair_uuid)
        self.assertEqual(updated["state"], "Repairing")

    def test_complete_action_to_pending_verification(self):
        self.service.start_repair(self.repair_uuid)
        updated = self.service.complete_action(self.repair_uuid)
        self.assertEqual(updated["state"], "PendingVerification")

    def test_verify_passed_to_resolved(self):
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        updated = self.service.verify(self.repair_uuid, passed=True)
        self.assertEqual(updated["state"], "Resolved")

    def test_verify_failed_back_to_needs_repair(self):
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        updated = self.service.verify(self.repair_uuid, passed=False)
        self.assertEqual(updated["state"], "NeedsRepair")

    def test_verify_stores_result(self):
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        updated = self.service.verify(self.repair_uuid, True, result="all checks passed")
        self.assertEqual(updated["verification_result"], "all checks passed")

    def test_ignore_from_needs_repair(self):
        updated = self.service.ignore(self.repair_uuid)
        self.assertEqual(updated["state"], "Ignored")


class TestRepairServiceLifecycleAssisted(unittest.TestCase):
    """Assisted repairs require confirmation before start."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.repair_repo = repo.RepairRepository(factory)
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.RepairService(self.repair_repo, self.issue_repo)
        result = self.service.detect("op-1", "album-1", "/path", category="Assisted")
        self.repair_uuid = result["repair"]["uuid"]

    def test_start_repair_without_confirmation_raises(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.start_repair(self.repair_uuid)

    def test_confirm_stores_text(self):
        updated = self.service.confirm(self.repair_uuid, "I agree to rename")
        self.assertEqual(updated["confirmation"], "I agree to rename")

    def test_start_repair_after_confirm_succeeds(self):
        self.service.confirm(self.repair_uuid, "Confirmed")
        updated = self.service.start_repair(self.repair_uuid)
        self.assertEqual(updated["state"], "Repairing")

    def test_full_assisted_flow(self):
        self.service.confirm(self.repair_uuid, "OK")
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        updated = self.service.verify(self.repair_uuid, True)
        self.assertEqual(updated["state"], "Resolved")


class TestRepairServiceManualConflict(unittest.TestCase):
    """ManualConflict path through the state machine."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.repair_repo = repo.RepairRepository(factory)
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.RepairService(self.repair_repo, self.issue_repo)
        result = self.service.detect("op-1", "album-1", "/path")
        self.repair_uuid = result["repair"]["uuid"]

    def test_escalate_to_manual_from_needs_repair(self):
        updated = self.service.escalate_to_manual(self.repair_uuid)
        self.assertEqual(updated["state"], "ManualConflict")

    def test_ignore_from_manual_conflict(self):
        self.service.escalate_to_manual(self.repair_uuid)
        updated = self.service.ignore(self.repair_uuid)
        self.assertEqual(updated["state"], "Ignored")

    def test_start_repair_from_manual_conflict_requires_confirmation(self):
        self.service.escalate_to_manual(self.repair_uuid)
        with self.assertRaises(svc.ServiceConflict):
            self.service.start_repair(self.repair_uuid)

    def test_full_manual_conflict_flow(self):
        self.service.escalate_to_manual(self.repair_uuid)
        self.service.confirm(self.repair_uuid, "User resolved conflict")
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        updated = self.service.verify(self.repair_uuid, True)
        self.assertEqual(updated["state"], "Resolved")


class TestRepairServiceInvalidTransitions(unittest.TestCase):
    """Invalid state transitions raise ServiceConflict."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.repair_repo = repo.RepairRepository(factory)
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.RepairService(self.repair_repo, self.issue_repo)
        result = self.service.detect("op-1", "album-1", "/path", category="Automatic")
        self.repair_uuid = result["repair"]["uuid"]

    def test_complete_action_from_needs_repair_raises(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.complete_action(self.repair_uuid)

    def test_verify_from_needs_repair_raises(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.verify(self.repair_uuid, True)

    def test_start_repair_from_repairing_raises(self):
        self.service.start_repair(self.repair_uuid)
        with self.assertRaises(svc.ServiceConflict):
            self.service.start_repair(self.repair_uuid)

    def test_ignore_from_resolved_raises(self):
        self.service.start_repair(self.repair_uuid)
        self.service.complete_action(self.repair_uuid)
        self.service.verify(self.repair_uuid, True)
        with self.assertRaises(svc.ServiceConflict):
            self.service.ignore(self.repair_uuid)

    def test_start_repair_nonexistent_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.start_repair("nonexistent")

    def test_ignore_nonexistent_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.ignore("nonexistent")

    def test_verify_from_repairing_raises(self):
        self.service.start_repair(self.repair_uuid)
        with self.assertRaises(svc.ServiceConflict):
            self.service.verify(self.repair_uuid, True)


# ---------------------------------------------------------------------------
# IssueService — lifecycle tests
# ---------------------------------------------------------------------------

class TestIssueServiceCreate(unittest.TestCase):
    """IssueService.create() returns an Open issue."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.IssueService(self.issue_repo)

    def _minimal(self):
        return {
            "category": "Repair",
            "description": "Album directory missing",
            "source_workflow": "RepairService",
        }

    def test_returns_dict(self):
        result = self.service.create(self._minimal())
        self.assertIsInstance(result, dict)

    def test_default_state_is_open(self):
        result = self.service.create(self._minimal())
        self.assertEqual(result["state"], "Open")

    def test_category_persisted(self):
        result = self.service.create(self._minimal())
        self.assertEqual(result["category"], "Repair")

    def test_description_persisted(self):
        result = self.service.create(self._minimal())
        self.assertEqual(result["description"], "Album directory missing")

    def test_all_documented_categories_can_be_created(self):
        for category in svc.ISSUE_CATEGORIES:
            issue = self.service.create({
                "category": category,
                "description": f"{category} issue",
                "source_workflow": "IntegrationTest",
            })
            self.assertEqual(issue["category"], category)

    def test_unsupported_category_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.create({
                "category": "Other",
                "description": "unsupported",
                "source_workflow": "IntegrationTest",
            })

    def test_device_registration_can_create_a_linked_issue(self):
        auth = svc.AuthenticationService(
            repo.AuthRepository(lambda: self.conn),
            registration_secret="registration-proof",
            issue_service=self.service,
        )
        registration = auth.request_registration(
            device_name="AI Worker",
            device_identity="ai-worker-issue-test",
            requested_role="writer",
            requested_scopes=None,
            registration_proof="registration-proof",
        )
        rows = self.conn.execute(
            "SELECT uuid FROM issue WHERE category = 'Device Registration'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            self.issue_repo.list_links(rows[0]["uuid"])[0]["target_uuid"], registration["uuid"]
        )


class TestIssueServiceLifecycle(unittest.TestCase):
    """IssueService state transitions."""

    def setUp(self):
        self.conn = _make_db()
        factory = lambda: self.conn
        self.issue_repo = repo.IssueRepository(factory)
        self.service = svc.IssueService(self.issue_repo)
        self.issue = self.service.create({
            "category": "Repair",
            "description": "test",
            "source_workflow": "RepairService",
        })
        self.issue_uuid = self.issue["uuid"]

    def test_begin_work_transitions_to_in_progress(self):
        updated = self.service.begin_work(self.issue_uuid)
        self.assertEqual(updated["state"], "InProgress")

    def test_reopen_transitions_to_open(self):
        self.service.begin_work(self.issue_uuid)
        updated = self.service.reopen(self.issue_uuid)
        self.assertEqual(updated["state"], "Open")

    def test_resolve_transitions_to_resolved(self):
        self.service.begin_work(self.issue_uuid)
        updated = self.service.resolve(
            self.issue_uuid, "Validated by the originating workflow", actor_role="admin"
        )
        self.assertEqual(updated["state"], "Resolved")
        self.assertEqual(updated["resolved_by"], "admin")

    def test_archive_from_open(self):
        updated = self.service.archive(self.issue_uuid, actor_role="admin")
        self.assertEqual(updated["state"], "Archived")

    def test_archive_from_resolved(self):
        self.service.begin_work(self.issue_uuid)
        self.service.resolve(self.issue_uuid, "verified", actor_role="admin")
        updated = self.service.archive(self.issue_uuid, actor_role="admin")
        self.assertEqual(updated["state"], "Archived")

    def test_full_happy_path(self):
        self.service.begin_work(self.issue_uuid)
        self.service.resolve(self.issue_uuid, "verified", actor_role="admin")
        updated = self.service.archive(self.issue_uuid, actor_role="admin")
        self.assertEqual(updated["state"], "Archived")

    def test_begin_work_nonexistent_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.begin_work("nonexistent")

    def test_archive_from_archived_raises(self):
        self.service.archive(self.issue_uuid, actor_role="admin")
        with self.assertRaises(svc.ServiceConflict):
            self.service.archive(self.issue_uuid, actor_role="admin")

    def test_resolve_from_open_raises(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.resolve(self.issue_uuid, "verified", actor_role="admin")

    def test_reopen_from_open_raises(self):
        with self.assertRaises(svc.ServiceConflict):
            self.service.reopen(self.issue_uuid)

    def test_only_administrator_can_assign_resolve_or_archive(self):
        with self.assertRaises(svc.AuthorizationFailure):
            self.service.assign(self.issue_uuid, "Owner", actor_role="writer")
        self.service.begin_work(self.issue_uuid)
        with self.assertRaises(svc.AuthorizationFailure):
            self.service.resolve(self.issue_uuid, "verified", actor_role="writer")
        with self.assertRaises(svc.AuthorizationFailure):
            self.service.archive(self.issue_uuid, actor_role="writer")

    def test_assign_and_clear_owner_as_administrator(self):
        assigned = self.service.assign(self.issue_uuid, "Local Administrator", actor_role="admin")
        self.assertEqual(assigned["owner"], "Local Administrator")
        cleared = self.service.assign(self.issue_uuid, None, actor_role="admin")
        self.assertIsNone(cleared["owner"])

    def test_resolve_requires_verification(self):
        self.service.begin_work(self.issue_uuid)
        with self.assertRaises(ValueError):
            self.service.resolve(self.issue_uuid, "", actor_role="admin")

    def test_categorize_and_link_representative_cross_cutting_records(self):
        categorized = self.service.categorize(self.issue_uuid, "Security")
        self.assertEqual(categorized["category"], "Security")
        links = self.service.link(self.issue_uuid, "triggering_operation", "validation-op")
        links = self.service.link(self.issue_uuid, "affected_entity", "device-registration")
        self.assertEqual(
            {(link["relationship"], link["target_uuid"]) for link in links},
            {("triggering_operation", "validation-op"), ("affected_entity", "device-registration")},
        )

    def test_invalid_link_relationship_is_rejected(self):
        with self.assertRaises(ValueError):
            self.service.link(self.issue_uuid, "unknown", "target")

    def test_cross_cutting_workflows_can_create_and_link_issues(self):
        workflows = {
            "Validation": "validation-operation",
            "Filesystem": "filesystem-operation",
            "Import": "import-operation",
            "Repair": "repair-operation",
            "AI Processing": "ai-operation",
            "Security": "security-operation",
            "Device Registration": "device-registration-operation",
        }
        for category, operation_uuid in workflows.items():
            issue = self.service.create({
                "category": category,
                "description": f"{category} requires review",
                "source_workflow": category,
            })
            links = self.service.link(issue["uuid"], "triggering_operation", operation_uuid)
            self.assertEqual(links[0]["target_uuid"], operation_uuid)


# ---------------------------------------------------------------------------
# OperationService — operation logging tests (BT-012)
# ---------------------------------------------------------------------------

def _make_op_service(conn):
    op_repo = repo.OperationRepository(_db_factory(conn))
    return svc.OperationService(op_repo), op_repo


class TestOperationServiceBegin(unittest.TestCase):
    """OperationService.begin() creates a durable Operation record."""

    def setUp(self):
        self.conn = _make_db()
        self.service, self.op_repo = _make_op_service(self.conn)

    def test_returns_dict(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertIsInstance(result, dict)

    def test_default_status_is_running(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertEqual(result["status"], svc.OP_STATUS_RUNNING)

    def test_pending_status_stored(self):
        result = self.service.begin(
            "import_execution", svc.OP_INITIATOR_WEB_UI,
            status=svc.OP_STATUS_PENDING,
        )
        self.assertEqual(result["status"], svc.OP_STATUS_PENDING)

    def test_operation_type_stored(self):
        result = self.service.begin("bulk_delete", svc.OP_INITIATOR_WEB_UI)
        self.assertEqual(result["operation_type"], "bulk_delete")

    def test_initiator_stored(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_AI_WORKER)
        self.assertEqual(result["initiator"], svc.OP_INITIATOR_AI_WORKER)

    def test_uuid_assigned(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertIsNotNone(result["uuid"])

    def test_started_at_populated(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertIsNotNone(result["started_at"])

    def test_ended_at_none(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertIsNone(result["ended_at"])

    def test_import_uuid_stored(self):
        result = self.service.begin(
            "import_execution", svc.OP_INITIATOR_WEB_UI,
            import_uuid="imp-123",
        )
        self.assertEqual(result["import_uuid"], "imp-123")

    def test_entity_uuid_stored(self):
        result = self.service.begin(
            "album_create", svc.OP_INITIATOR_WEB_UI,
            entity_uuid="alb-abc",
        )
        self.assertEqual(result["entity_uuid"], "alb-abc")

    def test_repair_uuid_stored(self):
        result = self.service.begin(
            "repair_action", svc.OP_INITIATOR_WEB_UI,
            repair_uuid="rep-xyz",
        )
        self.assertEqual(result["repair_uuid"], "rep-xyz")

    def test_related_operation_uuid_stored(self):
        result = self.service.begin(
            "repair_action", svc.OP_INITIATOR_WEB_UI,
            related_operation_uuid="op-original",
        )
        self.assertEqual(result["related_operation_uuid"], "op-original")

    def test_record_is_durable(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        fetched = self.op_repo.get_by_uuid(result["uuid"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["operation_type"], "import_execution")

    def test_shape_has_all_required_keys(self):
        result = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        for key in (
            "uuid", "operation_type", "initiator", "status",
            "started_at", "ended_at", "summary",
            "entity_uuid", "import_uuid", "batch_uuid",
            "error_category", "error_code", "error_details",
        ):
            self.assertIn(key, result)


class TestOperationServiceSucceed(unittest.TestCase):
    """OperationService.succeed() marks the Operation Succeeded."""

    def setUp(self):
        self.conn = _make_db()
        self.service, self.op_repo = _make_op_service(self.conn)
        self.op = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.op_uuid = self.op["uuid"]

    def test_status_becomes_succeeded(self):
        result = self.service.succeed(self.op_uuid)
        self.assertEqual(result["status"], svc.OP_STATUS_SUCCEEDED)

    def test_summary_stored(self):
        result = self.service.succeed(self.op_uuid, summary="Imported 5 albums")
        self.assertEqual(result["summary"], "Imported 5 albums")

    def test_ended_at_populated(self):
        result = self.service.succeed(self.op_uuid)
        self.assertIsNotNone(result["ended_at"])

    def test_not_found_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.succeed("nonexistent")

    def test_already_failed_raises_conflict(self):
        self.service.fail(
            self.op_uuid, "filesystem", "filesystem.write-failed"
        )
        with self.assertRaises(svc.ServiceConflict):
            self.service.succeed(self.op_uuid)

    def test_already_needs_repair_raises_conflict(self):
        self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed"
        )
        with self.assertRaises(svc.ServiceConflict):
            self.service.succeed(self.op_uuid)

    def test_already_cancelled_raises_conflict(self):
        self.service.cancel(self.op_uuid)
        with self.assertRaises(svc.ServiceConflict):
            self.service.succeed(self.op_uuid)


class TestOperationServiceFail(unittest.TestCase):
    """OperationService.fail() marks the Operation Failed with error fields."""

    def setUp(self):
        self.conn = _make_db()
        self.service, _ = _make_op_service(self.conn)
        self.op = self.service.begin("bulk_import", svc.OP_INITIATOR_WEB_UI)
        self.op_uuid = self.op["uuid"]

    def test_status_becomes_failed(self):
        result = self.service.fail(self.op_uuid, "filesystem", "filesystem.write-failed")
        self.assertEqual(result["status"], svc.OP_STATUS_FAILED)

    def test_error_category_stored(self):
        result = self.service.fail(self.op_uuid, "filesystem", "filesystem.write-failed")
        self.assertEqual(result["error_category"], "filesystem")

    def test_error_code_stored(self):
        result = self.service.fail(self.op_uuid, "filesystem", "filesystem.write-failed")
        self.assertEqual(result["error_code"], "filesystem.write-failed")

    def test_error_details_stored(self):
        result = self.service.fail(
            self.op_uuid, "database", "database.transaction-failed",
            error_details="UNIQUE constraint failed"
        )
        self.assertEqual(result["error_details"], "UNIQUE constraint failed")

    def test_summary_stored(self):
        result = self.service.fail(
            self.op_uuid, "filesystem", "filesystem.write-failed",
            summary="Could not write to archive"
        )
        self.assertEqual(result["summary"], "Could not write to archive")

    def test_ended_at_populated(self):
        result = self.service.fail(self.op_uuid, "filesystem", "filesystem.write-failed")
        self.assertIsNotNone(result["ended_at"])

    def test_not_found_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.fail("nonexistent", "filesystem", "filesystem.write-failed")


class TestOperationServiceNeedsRepair(unittest.TestCase):
    """OperationService.mark_needs_repair() marks NeedsRepair and stores repair context."""

    def setUp(self):
        self.conn = _make_db()
        self.service, _ = _make_op_service(self.conn)
        self.op = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.op_uuid = self.op["uuid"]

    def test_status_becomes_needs_repair(self):
        result = self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed"
        )
        self.assertEqual(result["status"], svc.OP_STATUS_NEEDS_REPAIR)

    def test_error_category_stored(self):
        result = self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed"
        )
        self.assertEqual(result["error_category"], "filesystem")

    def test_repair_state_stored(self):
        result = self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed",
            repair_state="NeedsRepair",
        )
        self.assertEqual(result["repair_state"], "NeedsRepair")

    def test_recovery_context_stored(self):
        result = self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed",
            recovery_context="Check disk permissions then retry",
        )
        self.assertEqual(result["recovery_context"], "Check disk permissions then retry")

    def test_ended_at_populated(self):
        result = self.service.mark_needs_repair(
            self.op_uuid, "filesystem", "filesystem.write-failed"
        )
        self.assertIsNotNone(result["ended_at"])

    def test_not_found_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.mark_needs_repair("nonexistent", "filesystem", "filesystem.write-failed")


class TestOperationServiceCancel(unittest.TestCase):
    """OperationService.cancel() marks the Operation Cancelled."""

    def setUp(self):
        self.conn = _make_db()
        self.service, _ = _make_op_service(self.conn)
        self.op = self.service.begin("workspace_promotion", svc.OP_INITIATOR_WEB_UI)
        self.op_uuid = self.op["uuid"]

    def test_status_becomes_cancelled(self):
        result = self.service.cancel(self.op_uuid)
        self.assertEqual(result["status"], svc.OP_STATUS_CANCELLED)

    def test_summary_stored(self):
        result = self.service.cancel(self.op_uuid, summary="User cancelled the operation")
        self.assertEqual(result["summary"], "User cancelled the operation")

    def test_ended_at_populated(self):
        result = self.service.cancel(self.op_uuid)
        self.assertIsNotNone(result["ended_at"])

    def test_not_found_raises(self):
        with self.assertRaises(svc.ServiceNotFound):
            self.service.cancel("nonexistent")


class TestOperationServiceWorkflowIntegration(unittest.TestCase):
    """OperationService records represent material write workflows."""

    def setUp(self):
        self.conn = _make_db()
        self.service, self.op_repo = _make_op_service(self.conn)

    def test_import_execution_workflow(self):
        """Import execution creates a Running operation and succeeds."""
        import_uuid = "imp-001"
        op = self.service.begin(
            "import_execution",
            svc.OP_INITIATOR_WEB_UI,
            import_uuid=import_uuid,
            summary="Importing 3 albums",
        )
        op_uuid = op["uuid"]
        self.assertEqual(op["status"], svc.OP_STATUS_RUNNING)
        self.assertEqual(op["import_uuid"], import_uuid)

        result = self.service.succeed(op_uuid, summary="Successfully imported 3 albums")
        self.assertEqual(result["status"], svc.OP_STATUS_SUCCEEDED)
        self.assertEqual(result["import_uuid"], import_uuid)

    def test_import_execution_filesystem_failure(self):
        """Filesystem failure after DB write becomes NeedsRepair, not Failed."""
        op = self.service.begin(
            "import_execution",
            svc.OP_INITIATOR_WEB_UI,
            import_uuid="imp-002",
        )
        op_uuid = op["uuid"]

        result = self.service.mark_needs_repair(
            op_uuid,
            "filesystem",
            "filesystem.write-failed",
            summary="Album directory could not be created",
            repair_state="NeedsRepair",
            recovery_context="Retry after checking disk permissions",
        )
        self.assertEqual(result["status"], svc.OP_STATUS_NEEDS_REPAIR)
        self.assertIsNotNone(result["error_category"])

    def test_bulk_import_workflow_with_batch_uuid(self):
        """Bulk import uses batch_uuid contextual UUID."""
        batch_uuid = "batch-abc"
        op = self.service.begin(
            "bulk_import",
            svc.OP_INITIATOR_WEB_UI,
            batch_uuid=batch_uuid,
        )
        self.assertEqual(op["batch_uuid"], batch_uuid)

    def test_repair_operation_references_original(self):
        """Repair operation links back to the original failed operation."""
        original = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.service.mark_needs_repair(
            original["uuid"], "filesystem", "filesystem.write-failed"
        )

        # Record the follow-up repair operation referencing the original.
        repair_op = self.service.begin(
            "repair_action",
            svc.OP_INITIATOR_WEB_UI,
            repair_uuid="rep-123",
            related_operation_uuid=original["uuid"],
        )
        self.assertEqual(repair_op["related_operation_uuid"], original["uuid"])

        # Completing repair does NOT change the original Operation to Succeeded.
        self.service.succeed(repair_op["uuid"])
        original_fetched = self.op_repo.get_by_uuid(original["uuid"])
        self.assertEqual(original_fetched["status"], svc.OP_STATUS_NEEDS_REPAIR)

    def test_snapshot_operation_records_outcome(self):
        """Snapshot and restore operations create Operation records."""
        op = self.service.begin(
            "snapshot",
            svc.OP_INITIATOR_SYSTEM,
            summary="Pre-import safety snapshot",
        )
        result = self.service.succeed(op["uuid"], summary="Snapshot created successfully")
        self.assertEqual(result["status"], svc.OP_STATUS_SUCCEEDED)
        self.assertEqual(result["initiator"], svc.OP_INITIATOR_SYSTEM)

    def test_operation_history_independent_per_record(self):
        """Each material write gets its own independent Operation record."""
        op1 = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        op2 = self.service.begin("import_execution", svc.OP_INITIATOR_WEB_UI)
        self.assertNotEqual(op1["uuid"], op2["uuid"])

        self.service.succeed(op1["uuid"])
        self.service.fail(op2["uuid"], "database", "database.transaction-failed")

        self.assertEqual(
            self.op_repo.get_by_uuid(op1["uuid"])["status"],
            svc.OP_STATUS_SUCCEEDED,
        )
        self.assertEqual(
            self.op_repo.get_by_uuid(op2["uuid"])["status"],
            svc.OP_STATUS_FAILED,
        )
