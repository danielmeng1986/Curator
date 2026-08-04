#!/usr/bin/env python3
"""Focused repository-layer tests for Curator Backend.

Each test class covers one repository class. Tests use an in-memory SQLite
database so they run without any real database or filesystem.

Persistence correctness (SQL round-trips, conflict detection, transaction
atomicity, field filtering) is verified here. Business rules and HTTP concerns
are verified in test_services.py and test_api_contract.py respectively.
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import repositories as repo


# ---------------------------------------------------------------------------
# Shared test database helpers
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
    album_id INTEGER,
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
);
"""


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    return conn


def _db_factory(conn: sqlite3.Connection):
    return lambda: conn


# ---------------------------------------------------------------------------
# StatusRepository
# ---------------------------------------------------------------------------

class TestStatusRepositoryListWithCounts(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO status (name, description) VALUES ('New', 'fresh')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, status_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'AlbumA', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, status_id)"
            " VALUES ('S', 1)"
        )
        self.conn.commit()
        self.repo = repo.StatusRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_returns_status_with_counts(self):
        rows = self.repo.list_with_counts()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "New")
        self.assertEqual(rows[0]["album_count"], 1)
        self.assertEqual(rows[0]["workspace_album_count"], 1)

    def test_zero_counts_when_unreferenced(self):
        self.conn.execute("INSERT INTO status (name) VALUES ('Unused')")
        self.conn.commit()
        rows = self.repo.list_with_counts()
        unused = next(r for r in rows if r["name"] == "Unused")
        self.assertEqual(unused["album_count"], 0)
        self.assertEqual(unused["workspace_album_count"], 0)


class TestStatusRepositoryCreate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.StatusRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_create_returns_id_and_record(self):
        result = self.repo.create("Active", "in progress")
        self.assertIn("id", result)
        self.assertEqual(result["status"]["name"], "Active")

    def test_create_persists_to_db(self):
        result = self.repo.create("Active", "desc")
        row = self.conn.execute(
            "SELECT name FROM status WHERE id = ?", (result["id"],)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Active")


class TestStatusRepositoryUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO status (name, description) VALUES ('Old', 'old desc')"
        )
        self.conn.commit()
        self.repo = repo.StatusRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_update_returns_refreshed_record(self):
        result = self.repo.update(1, "New", "new desc")
        self.assertEqual(result["name"], "New")
        self.assertEqual(result["description"], "new desc")

    def test_update_returns_none_for_missing_id(self):
        result = self.repo.update(999, "X", "Y")
        self.assertIsNone(result)


class TestStatusRepositoryDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO status (name) VALUES ('Deletable')"
        )
        self.conn.commit()
        self.repo = repo.StatusRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_status_succeeds(self):
        self.repo.delete(1)
        row = self.conn.execute("SELECT id FROM status WHERE id = 1").fetchone()
        self.assertIsNone(row)

    def test_delete_raises_conflict_when_album_references(self):
        self.conn.execute(
            "INSERT INTO album (uuid, status_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        with self.assertRaises(repo.PersistenceConflict) as ctx:
            self.repo.delete(1)
        self.assertIn("album_refs", ctx.exception.details)
        self.assertEqual(ctx.exception.details["album_refs"], 1)

    def test_delete_raises_conflict_when_workspace_album_references(self):
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, status_id) VALUES ('S', 1)"
        )
        self.conn.commit()
        with self.assertRaises(repo.PersistenceConflict) as ctx:
            self.repo.delete(1)
        self.assertIn("workspace_album_refs", ctx.exception.details)
        self.assertEqual(ctx.exception.details["workspace_album_refs"], 1)


# ---------------------------------------------------------------------------
# ModelRepository
# ---------------------------------------------------------------------------

class TestModelRepositorySearch(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m2', 'Bob', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_empty_query_returns_all(self):
        rows, total = self.repo.search("", limit=50, offset=0)
        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 2)

    def test_search_filters_by_display_name(self):
        rows, total = self.repo.search("Ali", limit=50, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["display_name"], "Alice")

    def test_search_pagination(self):
        rows, total = self.repo.search("", limit=1, offset=0)
        self.assertEqual(total, 2)
        self.assertEqual(len(rows), 1)


class TestModelRepositoryUpdateFields(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_update_fields_returns_refreshed_record(self):
        result = self.repo.update_fields(
            1, {"display_name": "Alicia", "country": "US"}, "2024-06-01"
        )
        self.assertEqual(result["display_name"], "Alicia")
        self.assertEqual(result["country"], "US")
        self.assertEqual(result["updated_at"], "2024-06-01")

    def test_update_fields_returns_none_for_missing_id(self):
        result = self.repo.update_fields(999, {"display_name": "X"}, "2024-01-01")
        self.assertIsNone(result)


class TestModelRepositoryDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_model_succeeds(self):
        self.repo.delete(1)
        row = self.conn.execute("SELECT id FROM model WHERE id = 1").fetchone()
        self.assertIsNone(row)

    def test_delete_raises_conflict_when_album_model_exists(self):
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.commit()
        with self.assertRaises(repo.PersistenceConflict) as ctx:
            self.repo.delete(1)
        self.assertIn("album_refs", ctx.exception.details)


class TestModelRepositoryFindByName(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, primary_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', 'Ali', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_find_by_display_name(self):
        result = self.repo.find_by_name("Alice")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 1)

    def test_find_by_primary_name(self):
        result = self.repo.find_by_name("Ali")
        self.assertIsNotNone(result)

    def test_find_by_name_case_insensitive(self):
        result = self.repo.find_by_name("ALICE")
        self.assertIsNotNone(result)

    def test_find_by_name_returns_none_when_not_found(self):
        result = self.repo.find_by_name("Nobody")
        self.assertIsNone(result)


class TestModelRepositoryFindOrCreate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_creates_new_model_when_absent(self):
        model_id = self.repo.find_or_create("NewModel", "2024-01-01")
        row = self.conn.execute(
            "SELECT display_name FROM model WHERE id = ?", (model_id,)
        ).fetchone()
        self.assertEqual(row[0], "NewModel")

    def test_returns_existing_model_id(self):
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Existing', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        model_id = self.repo.find_or_create("existing", "2024-06-01")
        count = self.conn.execute("SELECT COUNT(*) FROM model").fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(model_id, 1)


# ---------------------------------------------------------------------------
# StudioRepository
# ---------------------------------------------------------------------------

class TestStudioRepositorySearch(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s2', 'Viv', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_returns_all_when_empty_query(self):
        rows, total = self.repo.search("", limit=50, offset=0)
        self.assertEqual(total, 2)

    def test_search_filters_by_name(self):
        rows, total = self.repo.search("Met", limit=50, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["name"], "MetArt")


class TestStudioRepositoryGetById(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Shoot1', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_get_by_id_returns_studio_and_albums(self):
        result = self.repo.get_by_id(1)
        self.assertIsNotNone(result)
        self.assertEqual(result["studio"]["name"], "MetArt")
        self.assertEqual(len(result["albums"]), 1)

    def test_get_by_id_returns_none_for_missing_id(self):
        result = self.repo.get_by_id(999)
        self.assertIsNone(result)


class TestStudioRepositoryCreate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_create_returns_id_and_record(self):
        result = self.repo.create({"name": "NewStudio", "website": "http://x.com"})
        self.assertIn("id", result)
        self.assertEqual(result["studio"]["name"], "NewStudio")

    def test_create_persists_to_db(self):
        result = self.repo.create({"name": "NewStudio"})
        row = self.conn.execute(
            "SELECT name FROM studio WHERE id = ?", (result["id"],)
        ).fetchone()
        self.assertIsNotNone(row)


class TestStudioRepositoryUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'OldName', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_update_returns_refreshed_record(self):
        result = self.repo.update(1, {"name": "NewName"}, "2024-06-01")
        self.assertEqual(result["name"], "NewName")
        self.assertEqual(result["updated_at"], "2024-06-01")

    def test_update_returns_none_for_missing_id(self):
        result = self.repo.update(999, {"name": "X"}, "2024-06-01")
        self.assertIsNone(result)


class TestStudioRepositoryDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'S', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_unreferenced_studio_succeeds(self):
        self.repo.delete(1)
        row = self.conn.execute("SELECT id FROM studio WHERE id = 1").fetchone()
        self.assertIsNone(row)

    def test_delete_raises_conflict_when_album_references(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        with self.assertRaises(repo.PersistenceConflict) as ctx:
            self.repo.delete(1)
        self.assertIn("album_refs", ctx.exception.details)
        self.assertEqual(ctx.exception.details["album_refs"], 1)


# ---------------------------------------------------------------------------
# AlbumRepository
# ---------------------------------------------------------------------------

class TestAlbumRepositoryCreate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'S', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_create_returns_album_id(self):
        album_id = self.repo.create(
            {"studio_id": 1, "title": "Shoot1"},
            models=[{"model_id": 1, "role": "lead"}],
            relations=[],
            now="2024-06-01",
        )
        self.assertIsInstance(album_id, int)

    def test_create_inserts_album_model_rows(self):
        album_id = self.repo.create(
            {"studio_id": 1, "title": "Shoot1"},
            models=[{"model_id": 1}],
            relations=[],
            now="2024-06-01",
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = ?", (album_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_create_inserts_relation_rows(self):
        other_id = self.repo.create(
            {"studio_id": 1, "title": "Other"},
            models=[],
            relations=[],
            now="2024-06-01",
        )
        album_id = self.repo.create(
            {"studio_id": 1, "title": "Shoot1"},
            models=[],
            relations=[{"related_album_id": other_id, "relation_type": "set"}],
            now="2024-06-01",
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_relation WHERE album_id = ?", (album_id,)
        ).fetchone()[0]
        self.assertEqual(count, 1)


class TestAlbumRepositoryUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'S', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m2', 'Bob', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_update_replaces_model_list(self):
        self.repo.update(
            1,
            {"studio_id": 1, "title": "T2"},
            models=[{"model_id": 2}],
            relations=[],
            now="2024-06-01",
        )
        rows = self.conn.execute(
            "SELECT model_id FROM album_model WHERE album_id = 1"
        ).fetchall()
        model_ids = [r[0] for r in rows]
        self.assertEqual(model_ids, [2])

    def test_update_clears_models_when_empty_list(self):
        self.repo.update(
            1,
            {"studio_id": 1, "title": "T2"},
            models=[],
            relations=[],
            now="2024-06-01",
        )
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)


class TestAlbumRepositoryDelete(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.execute(
            "INSERT INTO photo (uuid, album_id, filename, created_at)"
            " VALUES ('p1', 1, 'img.jpg', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_delete_removes_album(self):
        self.repo.delete(1)
        row = self.conn.execute("SELECT id FROM album WHERE id = 1").fetchone()
        self.assertIsNone(row)

    def test_delete_cascades_to_album_model(self):
        self.repo.delete(1)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)

    def test_delete_cascades_to_photos(self):
        self.repo.delete(1)
        count = self.conn.execute(
            "SELECT COUNT(*) FROM photo WHERE album_id = 1"
        ).fetchone()[0]
        self.assertEqual(count, 0)


# ---------------------------------------------------------------------------
# AlbumModelRepository
# ---------------------------------------------------------------------------

class TestAlbumModelRepository(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_add_returns_new_row_id(self):
        am_id = self.repo.add(1, {"model_id": 1, "role": "lead"})
        self.assertIsInstance(am_id, int)

    def test_add_persists_to_db(self):
        self.repo.add(1, {"model_id": 1, "role": "lead"})
        row = self.conn.execute(
            "SELECT role FROM album_model WHERE album_id = 1"
        ).fetchone()
        self.assertEqual(row[0], "lead")

    def test_update_changes_row(self):
        am_id = self.repo.add(1, {"model_id": 1, "role": "lead"})
        self.repo.update(1, am_id, {"role": "supporting", "remarks": "edited"})
        row = self.conn.execute(
            "SELECT role, remarks FROM album_model WHERE id = ?", (am_id,)
        ).fetchone()
        self.assertEqual(row[0], "supporting")
        self.assertEqual(row[1], "edited")

    def test_delete_removes_row(self):
        am_id = self.repo.add(1, {"model_id": 1})
        self.repo.delete(1, am_id)
        row = self.conn.execute(
            "SELECT id FROM album_model WHERE id = ?", (am_id,)
        ).fetchone()
        self.assertIsNone(row)


# ---------------------------------------------------------------------------
# AlbumRelationRepository
# ---------------------------------------------------------------------------

class TestAlbumRelationRepository(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T1', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a2', 'T2', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRelationRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_add_returns_new_row_id(self):
        rel_id = self.repo.add(1, {"related_album_id": 2, "relation_type": "set"})
        self.assertIsInstance(rel_id, int)

    def test_add_persists_to_db(self):
        self.repo.add(1, {"related_album_id": 2, "relation_type": "set"})
        row = self.conn.execute(
            "SELECT relation_type FROM album_relation WHERE album_id = 1"
        ).fetchone()
        self.assertEqual(row[0], "set")

    def test_update_changes_row(self):
        rel_id = self.repo.add(1, {"related_album_id": 2, "relation_type": "set"})
        self.repo.update(1, rel_id, {"relation_type": "sequel", "remarks": "note"})
        row = self.conn.execute(
            "SELECT relation_type, remarks FROM album_relation WHERE id = ?",
            (rel_id,),
        ).fetchone()
        self.assertEqual(row[0], "sequel")
        self.assertEqual(row[1], "note")

    def test_delete_removes_row(self):
        rel_id = self.repo.add(1, {"related_album_id": 2, "relation_type": "set"})
        self.repo.delete(1, rel_id)
        row = self.conn.execute(
            "SELECT id FROM album_relation WHERE id = ?", (rel_id,)
        ).fetchone()
        self.assertIsNone(row)


# ---------------------------------------------------------------------------
# PhotoRepository
# ---------------------------------------------------------------------------

class TestPhotoRepository(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.PhotoRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_add_returns_new_row_id(self):
        photo_id = self.repo.add(1, {"filename": "img.jpg", "width": 100, "height": 200})
        self.assertIsInstance(photo_id, int)

    def test_add_persists_to_db(self):
        photo_id = self.repo.add(1, {"filename": "img.jpg"})
        row = self.conn.execute(
            "SELECT filename FROM photo WHERE id = ?", (photo_id,)
        ).fetchone()
        self.assertEqual(row[0], "img.jpg")

    def test_update_changes_row(self):
        photo_id = self.repo.add(1, {"filename": "old.jpg"})
        self.repo.update(photo_id, {"filename": "new.jpg", "width": 800, "height": 600})
        row = self.conn.execute(
            "SELECT filename, width FROM photo WHERE id = ?", (photo_id,)
        ).fetchone()
        self.assertEqual(row[0], "new.jpg")
        self.assertEqual(row[1], 800)

    def test_delete_removes_row(self):
        photo_id = self.repo.add(1, {"filename": "img.jpg"})
        self.repo.delete(photo_id)
        row = self.conn.execute(
            "SELECT id FROM photo WHERE id = ?", (photo_id,)
        ).fetchone()
        self.assertIsNone(row)


# ---------------------------------------------------------------------------
# WorkspaceAlbumRepository
# ---------------------------------------------------------------------------

class TestWorkspaceAlbumRepositorySearch(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO status (name) VALUES ('New')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name, primary_model, status_id)"
            " VALUES ('MetArt', 'Shoot1', 'Alice', 1)"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name, primary_model)"
            " VALUES ('Viv', 'Session2', 'Bob')"
        )
        self.conn.commit()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_returns_all_when_no_filters(self):
        rows, total = self.repo.search(limit=50, offset=0)
        self.assertEqual(total, 2)

    def test_search_filters_by_status_id(self):
        rows, total = self.repo.search(status_id="1", limit=50, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["studio_name"], "MetArt")

    def test_search_filters_by_studio_name(self):
        rows, total = self.repo.search(studio_name="Viv", limit=50, offset=0)
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["album_name"], "Session2")

    def test_search_linked_yes_filter(self):
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a1', 'T', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "UPDATE workspace_album SET album_id = 1 WHERE id = 1"
        )
        self.conn.commit()
        rows, total = self.repo.search(linked="yes", limit=50, offset=0)
        self.assertEqual(total, 1)

    def test_search_linked_no_filter(self):
        rows, total = self.repo.search(linked="no", limit=50, offset=0)
        self.assertEqual(total, 2)


class TestWorkspaceAlbumRepositoryGetById(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name)"
            " VALUES ('S', 'A')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name, belongs_to_album_id)"
            " VALUES ('S', 'B', 1)"
        )
        self.conn.commit()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_get_by_id_returns_record(self):
        result = self.repo.get_by_id(1)
        self.assertIsNotNone(result)
        self.assertEqual(result["studio_name"], "S")

    def test_get_by_id_returns_none_for_missing(self):
        result = self.repo.get_by_id(999)
        self.assertIsNone(result)

    def test_get_by_id_includes_belongs_to(self):
        result = self.repo.get_by_id(2)
        self.assertIsNotNone(result["belongs_to"])
        self.assertEqual(result["belongs_to"]["id"], 1)

    def test_get_by_id_belongs_to_none_when_not_set(self):
        result = self.repo.get_by_id(1)
        self.assertIsNone(result["belongs_to"])


class TestWorkspaceAlbumRepositoryUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, remark)"
            " VALUES ('S', 'old')"
        )
        self.conn.commit()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))
        self._allowed = frozenset({"remark", "studio_name", "album_name"})

    def tearDown(self):
        self.conn.close()

    def test_update_applies_allowed_field(self):
        self.repo.update(1, self._allowed, {"remark": "updated"})
        row = self.conn.execute(
            "SELECT remark FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "updated")

    def test_update_filters_disallowed_fields(self):
        self.repo.update(1, self._allowed, {"remark": "ok", "bad_col": "evil"})
        row = self.conn.execute(
            "SELECT remark FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row[0], "ok")

    def test_update_raises_value_error_when_no_valid_fields(self):
        with self.assertRaises(ValueError):
            self.repo.update(1, self._allowed, {"bad_col": "evil"})


class TestWorkspaceAlbumRepositoryBatchUpdate(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, remark) VALUES ('S', 'a')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, remark) VALUES ('S', 'b')"
        )
        self.conn.commit()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))
        self._allowed = frozenset({"remark", "studio_name"})

    def tearDown(self):
        self.conn.close()

    def test_batch_update_returns_updated_count(self):
        count = self.repo.batch_update([1, 2], self._allowed, {"remark": "new"})
        self.assertEqual(count, 2)

    def test_batch_update_applies_to_all_ids(self):
        self.repo.batch_update([1, 2], self._allowed, {"remark": "tagged"})
        rows = self.conn.execute(
            "SELECT remark FROM workspace_album ORDER BY id"
        ).fetchall()
        self.assertEqual(rows[0][0], "tagged")
        self.assertEqual(rows[1][0], "tagged")

    def test_batch_update_raises_value_error_when_no_valid_fields(self):
        with self.assertRaises(ValueError):
            self.repo.batch_update([1], self._allowed, {"injected_col": "evil"})


# ---------------------------------------------------------------------------
# ImportRepository
# ---------------------------------------------------------------------------

class TestImportRepositoryLookupPreviewItem(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'ExistingShoot', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ImportRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_detects_existing_studio(self):
        result = self.repo.lookup_preview_item("MetArt", "Alice", "NewShoot")
        self.assertTrue(result["studio_exists"])
        self.assertEqual(result["studio_id"], 1)

    def test_detects_missing_studio(self):
        result = self.repo.lookup_preview_item("Unknown", "Alice", "Shoot")
        self.assertFalse(result["studio_exists"])
        self.assertIsNone(result["studio_id"])

    def test_detects_existing_model(self):
        result = self.repo.lookup_preview_item("MetArt", "Alice", "NewShoot")
        self.assertTrue(result["model_exists"])

    def test_detects_missing_model(self):
        result = self.repo.lookup_preview_item("MetArt", "Nobody", "NewShoot")
        self.assertFalse(result["model_exists"])

    def test_detects_existing_album(self):
        result = self.repo.lookup_preview_item("MetArt", "Alice", "ExistingShoot")
        self.assertTrue(result["album_exists"])
        self.assertIsNotNone(result["album_id"])

    def test_detects_missing_album(self):
        result = self.repo.lookup_preview_item("MetArt", "Alice", "NewShoot")
        self.assertFalse(result["album_exists"])
        self.assertIsNone(result["album_id"])


class TestImportRepositoryCreateItem(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.ImportRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_create_item_returns_created_status(self):
        result = self.repo.create_item(
            "MetArt", "Alice", "Shoot1", "/archive/path", "2024-06-01"
        )
        self.assertEqual(result["status"], "created")
        self.assertIsInstance(result["album_id"], int)

    def test_create_item_creates_studio(self):
        self.repo.create_item("NewStudio", "Alice", "S1", "/p", "2024-06-01")
        row = self.conn.execute(
            "SELECT name FROM studio WHERE LOWER(name) = 'newstudio'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_create_item_creates_model(self):
        self.repo.create_item("Studio", "NewModel", "S1", "/p", "2024-06-01")
        row = self.conn.execute(
            "SELECT display_name FROM model WHERE LOWER(display_name) = 'newmodel'"
        ).fetchone()
        self.assertIsNotNone(row)

    def test_create_item_creates_album_model_link(self):
        result = self.repo.create_item("S", "Alice", "Shoot1", "/p", "2024-06-01")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM album_model WHERE album_id = ?",
            (result["album_id"],),
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_create_item_returns_skipped_for_duplicate(self):
        self.repo.create_item("MetArt", "Alice", "Shoot1", "/p", "2024-06-01")
        result = self.repo.create_item("MetArt", "Alice", "Shoot1", "/p", "2024-06-01")
        self.assertEqual(result["status"], "skipped")

    def test_create_item_reuses_existing_studio(self):
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'Existing', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo.create_item("Existing", "Alice", "Shoot1", "/p", "2024-06-01")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM studio WHERE LOWER(name) = 'existing'"
        ).fetchone()[0]
        self.assertEqual(count, 1)


# ---------------------------------------------------------------------------
# Read-model normalization tests
# ---------------------------------------------------------------------------

class TestModelReadModelShape(unittest.TestCase):
    """Model read model has stable fields and a computed ``name``."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, primary_name, created_at, updated_at)"
            " VALUES ('u1', 'Alice', 'Ali', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, primary_name, created_at, updated_at)"
            " VALUES ('u2', NULL, 'Noname', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_result_has_exact_expected_keys(self):
        rows, _ = self.repo.search("", limit=50, offset=0)
        expected_keys = {
            "id", "uuid", "name", "display_name", "primary_name",
            "description", "country", "ethnicity", "eye_color",
            "natural_hair_color", "created_at", "updated_at",
        }
        for row in rows:
            self.assertEqual(set(row.keys()), expected_keys)

    def test_search_name_is_coalesced_from_display_name(self):
        rows, _ = self.repo.search("Alice", limit=50, offset=0)
        self.assertEqual(rows[0]["name"], "Alice")

    def test_search_name_falls_back_to_primary_name_when_display_absent(self):
        rows, _ = self.repo.search("Noname", limit=50, offset=0)
        self.assertEqual(rows[0]["name"], "Noname")

    def test_search_optional_fields_are_none_when_absent(self):
        rows, _ = self.repo.search("Noname", limit=50, offset=0)
        self.assertIsNone(rows[0]["display_name"])
        self.assertIsNone(rows[0]["description"])
        self.assertIsNone(rows[0]["country"])

    def test_update_fields_result_has_name_field(self):
        result = self.repo.update_fields(1, {"display_name": "Updated"}, "2024-06-01")
        self.assertIn("name", result)
        self.assertEqual(result["name"], "Updated")

    def test_update_fields_result_has_exact_expected_keys(self):
        result = self.repo.update_fields(1, {"display_name": "X"}, "2024-06-01")
        expected_keys = {
            "id", "uuid", "name", "display_name", "primary_name",
            "description", "country", "ethnicity", "eye_color",
            "natural_hair_color", "created_at", "updated_at",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_create_model_result_has_name_field(self):
        result = self.repo.create({"display_name": "NewModel", "primary_name": "NM"})
        self.assertIn("name", result["model"])
        self.assertEqual(result["model"]["name"], "NewModel")

    def test_create_model_name_falls_back_to_primary_name(self):
        result = self.repo.create({"primary_name": "OnlyPrimary"})
        self.assertEqual(result["model"]["name"], "OnlyPrimary")

    def test_get_by_id_model_has_name_field(self):
        result = self.repo.get_by_id(1)
        self.assertIn("name", result["model"])
        self.assertEqual(result["model"]["name"], "Alice")


class TestModelDetailAlbumAssocShape(unittest.TestCase):
    """Album associations in a model detail read model have stable fields."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, capture_date, created_at, updated_at)"
            " VALUES ('a1', 1, 'Shoot1', '2024-03-01', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id, age_when_shot, role)"
            " VALUES (1, 1, 25.0, 'lead')"
        )
        self.conn.commit()
        self.repo = repo.ModelRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_album_assoc_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {
            "id", "title", "capture_date", "age_when_shot", "role", "remarks", "studio_name",
        }
        for album in result["albums"]:
            self.assertEqual(set(album.keys()), expected_keys)

    def test_album_assoc_studio_name_is_populated(self):
        result = self.repo.get_by_id(1)
        self.assertEqual(result["albums"][0]["studio_name"], "MetArt")

    def test_album_assoc_optional_remarks_is_none(self):
        result = self.repo.get_by_id(1)
        self.assertIsNone(result["albums"][0]["remarks"])


class TestAlbumListReadModelShape(unittest.TestCase):
    """Album list read model has stable fields and ``model_names`` as a list."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m2', 'Bob', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Shoot1', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 1)"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id) VALUES (1, 2)"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a2', 'NoModels', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_result_has_exact_expected_keys(self):
        rows, _ = self.repo.search()
        expected_keys = {
            "id", "uuid", "title", "description", "scene", "location",
            "capture_date", "publish_date", "rating", "path",
            "studio_id", "status_id", "created_at", "updated_at",
            "studio_name", "status_name", "model_names",
        }
        for row in rows:
            self.assertEqual(set(row.keys()), expected_keys)

    def test_model_names_is_always_a_list(self):
        rows, _ = self.repo.search()
        for row in rows:
            self.assertIsInstance(row["model_names"], list)

    def test_model_names_contains_all_associated_names(self):
        rows, _ = self.repo.search(q="Shoot1")
        self.assertEqual(len(rows), 1)
        self.assertIn("Alice", rows[0]["model_names"])
        self.assertIn("Bob", rows[0]["model_names"])

    def test_model_names_is_empty_list_when_no_models(self):
        rows, _ = self.repo.search(q="NoModels")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model_names"], [])

    def test_optional_fields_are_none_when_absent(self):
        rows, _ = self.repo.search(q="NoModels")
        self.assertIsNone(rows[0]["description"])
        self.assertIsNone(rows[0]["studio_id"])
        self.assertIsNone(rows[0]["status_id"])
        self.assertIsNone(rows[0]["studio_name"])


class TestAlbumDetailReadModelShape(unittest.TestCase):
    """Album detail read model has stable fields; photo hash is excluded."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s1', 'MetArt', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO model (uuid, display_name, created_at, updated_at)"
            " VALUES ('m1', 'Alice', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Shoot1', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_model (album_id, model_id, role) VALUES (1, 1, 'lead')"
        )
        self.conn.execute(
            "INSERT INTO album (uuid, title, created_at, updated_at)"
            " VALUES ('a2', 'Related', '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO album_relation (album_id, related_album_id, relation_type)"
            " VALUES (1, 2, 'set')"
        )
        self.conn.execute(
            "INSERT INTO photo (uuid, album_id, filename, hash, width, height, created_at)"
            " VALUES ('p1', 1, 'img.jpg', 'abc123hash', 1920, 1080, '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.AlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_album_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {
            "id", "uuid", "title", "description", "scene", "location",
            "capture_date", "publish_date", "rating", "path",
            "studio_id", "status_id", "created_at", "updated_at",
            "studio_name", "status_name",
        }
        self.assertEqual(set(result["album"].keys()), expected_keys)

    def test_album_model_assoc_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {"id", "model_id", "age_when_shot", "role", "remarks", "model_name"}
        for m in result["models"]:
            self.assertEqual(set(m.keys()), expected_keys)

    def test_album_relation_assoc_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {
            "id", "related_album_id", "relation_type", "remarks",
            "related_title", "related_studio",
        }
        for r in result["relations"]:
            self.assertEqual(set(r.keys()), expected_keys)

    def test_photo_does_not_include_hash_field(self):
        result = self.repo.get_by_id(1)
        for p in result["photos"]:
            self.assertNotIn("hash", p)

    def test_photo_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {
            "id", "uuid", "album_id", "filename", "relative_path",
            "width", "height", "capture_time", "created_at",
        }
        for p in result["photos"]:
            self.assertEqual(set(p.keys()), expected_keys)

    def test_photo_album_id_matches_parent_album(self):
        result = self.repo.get_by_id(1)
        for p in result["photos"]:
            self.assertEqual(p["album_id"], 1)

    def test_album_model_assoc_model_name_populated(self):
        result = self.repo.get_by_id(1)
        self.assertEqual(result["models"][0]["model_name"], "Alice")

    def test_album_relation_assoc_related_title_populated(self):
        result = self.repo.get_by_id(1)
        self.assertEqual(result["relations"][0]["related_title"], "Related")


class TestWorkspaceAlbumReadModelShape(unittest.TestCase):
    """Workspace album read model has stable explicit fields."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO status (name) VALUES ('Active')"
        )
        self.conn.execute(
            "INSERT INTO workspace_album"
            " (uuid, studio_name, album_name, primary_model, status_id)"
            " VALUES ('wa-uuid-1', 'MetArt', 'Shoot1', 'Alice', 1)"
        )
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name)"
            " VALUES ('S', 'B')"
        )
        self.conn.commit()
        # Insert a child workspace album that references the first as its parent
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name, album_name, belongs_to_album_id)"
            " VALUES ('S', 'Child', 1)"
        )
        self.conn.commit()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_result_has_exact_expected_keys(self):
        rows, _ = self.repo.search(limit=50, offset=0)
        expected_keys = {
            "id", "uuid", "studio_name", "album_name", "primary_model",
            "additional_models", "remark", "current_path", "expected_path",
            "ai_result", "belongs_to_album_id", "album_id",
            "status_id", "status_name", "lifecycle_state",
        }
        for row in rows:
            self.assertEqual(set(row.keys()), expected_keys)

    def test_search_status_name_is_populated(self):
        rows, _ = self.repo.search(status_id="1", limit=50, offset=0)
        self.assertEqual(rows[0]["status_name"], "Active")

    def test_search_optional_fields_are_none_when_absent(self):
        rows, _ = self.repo.search(q="B", limit=50, offset=0)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["uuid"])
        self.assertIsNone(rows[0]["status_id"])
        self.assertIsNone(rows[0]["status_name"])

    def test_get_by_id_has_exact_expected_keys(self):
        result = self.repo.get_by_id(1)
        expected_keys = {
            "id", "uuid", "studio_name", "album_name", "primary_model",
            "additional_models", "remark", "current_path", "expected_path",
            "ai_result", "belongs_to_album_id", "album_id",
            "status_id", "status_name", "belongs_to", "linked_album",
            "lifecycle_state",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_get_by_id_belongs_to_has_expected_keys_when_present(self):
        result = self.repo.get_by_id(3)
        self.assertIsNotNone(result["belongs_to"])
        self.assertEqual(set(result["belongs_to"].keys()), {"id", "album_name", "primary_model"})

    def test_get_by_id_belongs_to_values_correct(self):
        result = self.repo.get_by_id(3)
        self.assertEqual(result["belongs_to"]["id"], 1)
        self.assertEqual(result["belongs_to"]["album_name"], "Shoot1")
        self.assertEqual(result["belongs_to"]["primary_model"], "Alice")

    def test_get_by_id_belongs_to_is_none_when_not_set(self):
        result = self.repo.get_by_id(1)
        self.assertIsNone(result["belongs_to"])

    def test_get_by_id_linked_album_is_none_when_not_linked(self):
        result = self.repo.get_by_id(1)
        self.assertIsNone(result["linked_album"])


class TestStudioReadModelShape(unittest.TestCase):
    """Studio read model has stable explicit fields."""

    def setUp(self):
        self.conn = _make_db()
        self.conn.execute(
            "INSERT INTO studio (uuid, name, website, description, media_scope,"
            " created_at, updated_at)"
            " VALUES ('s-uuid', 'MetArt', 'https://metart.com', 'desc', 'photos',"
            " '2024-01-01', '2024-01-01')"
        )
        self.conn.execute(
            "INSERT INTO studio (uuid, name, created_at, updated_at)"
            " VALUES ('s2-uuid', 'Minimal', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        self.repo = repo.StudioRepository(db_factory=_db_factory(self.conn))

    def tearDown(self):
        self.conn.close()

    def test_search_result_has_exact_expected_keys(self):
        rows, _ = self.repo.search("", limit=50, offset=0)
        expected_keys = {
            "id", "uuid", "name", "website", "description",
            "media_scope", "created_at", "updated_at",
        }
        for row in rows:
            self.assertEqual(set(row.keys()), expected_keys)

    def test_search_optional_fields_are_none_when_absent(self):
        rows, _ = self.repo.search("Minimal", limit=50, offset=0)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["website"])
        self.assertIsNone(rows[0]["description"])

    def test_update_result_has_exact_expected_keys(self):
        result = self.repo.update(1, {"name": "MetArt2"}, "2024-06-01")
        expected_keys = {
            "id", "uuid", "name", "website", "description",
            "media_scope", "created_at", "updated_at",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_get_by_id_studio_album_assoc_has_exact_expected_keys(self):
        self.conn.execute(
            "INSERT INTO album (uuid, studio_id, title, created_at, updated_at)"
            " VALUES ('a1', 1, 'Shoot1', '2024-01-01', '2024-01-01')"
        )
        self.conn.commit()
        result = self.repo.get_by_id(1)
        expected_album_keys = {"id", "title", "capture_date", "publish_date", "rating", "status_name"}
        for album in result["albums"]:
            self.assertEqual(set(album.keys()), expected_album_keys)


# ---------------------------------------------------------------------------
# WorkspaceAlbumRepository — creation and lifecycle-state persistence (BT-007)
# ---------------------------------------------------------------------------

class TestWorkspaceAlbumRepositoryCreate(unittest.TestCase):
    """Tests for WorkspaceAlbumRepository.create()."""

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))

    def test_create_returns_dict_with_id(self):
        result = self.repo.create({"studio_name": "Studio A", "album_name": "Album 1"})
        self.assertIn("id", result)
        self.assertIsNotNone(result["id"])

    def test_create_persists_lifecycle_state_active(self):
        result = self.repo.create({"studio_name": "Studio A", "album_name": "Album 1"})
        self.assertEqual(result["lifecycle_state"], "active")

    def test_create_persists_lifecycle_state_active_in_db(self):
        self.repo.create({"studio_name": "Studio A"})
        row = self.conn.execute(
            "SELECT lifecycle_state FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row["lifecycle_state"], "active")

    def test_create_persists_supplied_fields(self):
        result = self.repo.create(
            {"studio_name": "Studio B", "album_name": "Summer", "primary_model": "Alice"}
        )
        self.assertEqual(result["studio_name"], "Studio B")
        self.assertEqual(result["album_name"], "Summer")
        self.assertEqual(result["primary_model"], "Alice")

    def test_create_auto_generates_uuid(self):
        result = self.repo.create({"studio_name": "Studio A"})
        self.assertIsNotNone(result["uuid"])
        self.assertNotEqual(result["uuid"], "")

    def test_create_accepts_explicit_uuid(self):
        result = self.repo.create({"studio_name": "Studio A", "uuid": "test-uuid-123"})
        self.assertEqual(result["uuid"], "test-uuid-123")

    def test_create_read_model_has_lifecycle_state_key(self):
        result = self.repo.create({"studio_name": "Studio A"})
        self.assertIn("lifecycle_state", result)

    def test_create_ignores_lifecycle_state_in_caller_fields(self):
        # lifecycle_state must not be settable by callers at creation time.
        result = self.repo.create(
            {"studio_name": "Studio A", "lifecycle_state": "closed"}
        )
        self.assertEqual(result["lifecycle_state"], "active")

    def test_create_multiple_records_get_independent_ids(self):
        r1 = self.repo.create({"studio_name": "S1"})
        r2 = self.repo.create({"studio_name": "S2"})
        self.assertNotEqual(r1["id"], r2["id"])


class TestWorkspaceAlbumRepositoryLifecyclePersistence(unittest.TestCase):
    """Tests for WorkspaceAlbumRepository.get_lifecycle_state() and set_lifecycle_state()."""

    def setUp(self):
        self.conn = _make_db()
        self.repo = repo.WorkspaceAlbumRepository(db_factory=_db_factory(self.conn))
        self.conn.execute(
            "INSERT INTO workspace_album (studio_name) VALUES ('Studio A')"
        )
        self.conn.commit()

    def test_get_lifecycle_state_returns_active_by_default(self):
        self.assertEqual(self.repo.get_lifecycle_state(1), "active")

    def test_get_lifecycle_state_returns_none_for_missing_id(self):
        self.assertIsNone(self.repo.get_lifecycle_state(9999))

    def test_set_lifecycle_state_persists_review(self):
        self.repo.set_lifecycle_state(1, "review")
        self.assertEqual(self.repo.get_lifecycle_state(1), "review")

    def test_set_lifecycle_state_persists_closed(self):
        self.repo.set_lifecycle_state(1, "closed")
        self.assertEqual(self.repo.get_lifecycle_state(1), "closed")

    def test_set_lifecycle_state_persists_archived_retired(self):
        self.repo.set_lifecycle_state(1, "archived_retired")
        self.assertEqual(self.repo.get_lifecycle_state(1), "archived_retired")

    def test_set_lifecycle_state_is_durable(self):
        self.repo.set_lifecycle_state(1, "review")
        row = self.conn.execute(
            "SELECT lifecycle_state FROM workspace_album WHERE id = 1"
        ).fetchone()
        self.assertEqual(row["lifecycle_state"], "review")

    def test_norm_workspace_album_includes_lifecycle_state(self):
        self.repo.set_lifecycle_state(1, "review")
        record = self.repo.get_by_id(1)
        self.assertIn("lifecycle_state", record)
        self.assertEqual(record["lifecycle_state"], "review")


if __name__ == "__main__":
    unittest.main()