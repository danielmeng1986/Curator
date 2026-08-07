#!/usr/bin/env python3
"""Unit tests for migrate_curator_db_model_v02.py.

Covers:
- Equal current_path and expected_path → path = value
- Only current_path set → path = current_path
- Only expected_path set → path = expected_path
- Both null → path = null
- Conflicting paths (different non-null values) without --force-path → ConflictError
- Conflicting paths with --force-path=current → keep current_path
- Conflicting paths with --force-path=expected → keep expected_path
- Null workspace relation → skipped
- Self workspace relation (belongs_to_album_id == id) → skipped
- Valid cross-workspace relation → album_relation row created
- Permanent self-relation (both workspace rows resolve to same album) → skipped
- Missing target workspace row → skipped with invalid report
- Missing target album_id → skipped with invalid report
- Rerunning migration (idempotent) → no duplicates, no errors
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

# Make the scripts directory importable.
sys.path.insert(0, str(Path(__file__).parent))

from migrate_curator_db_model_v02 import (
    ConflictError,
    MigrationStats,
    create_album_relation_table,
    create_album_v02,
    get_columns,
    migrate_album_relations,
    migrate_album_table,
    verify,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def create_v01_schema(conn: sqlite3.Connection) -> None:
    """Create the v0.1 album and workspace_album tables (with current_path/expected_path)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS status (
            id INTEGER PRIMARY KEY, name TEXT, description TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studio (
            id INTEGER PRIMARY KEY, uuid TEXT UNIQUE, name TEXT,
            website TEXT, description TEXT, media_scope TEXT,
            created_at DATETIME, updated_at DATETIME
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE album (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL UNIQUE,
            studio_id INTEGER REFERENCES studio(id),
            status_id INTEGER REFERENCES status(id),
            title TEXT,
            description TEXT,
            scene TEXT,
            location TEXT,
            capture_date DATETIME,
            publish_date DATETIME,
            rating INTEGER,
            current_path TEXT,
            expected_path TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE workspace_album (
            id INTEGER PRIMARY KEY,
            current_path TEXT NOT NULL,
            expected_path TEXT,
            primary_model TEXT NOT NULL,
            studio_name TEXT NOT NULL,
            album_name TEXT NOT NULL,
            additional_models TEXT,
            status_id INTEGER,
            remark TEXT,
            belongs_to_album_id INTEGER,
            ai_result TEXT,
            album_id INTEGER REFERENCES album(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_workspace_album_album_id ON workspace_album(album_id)"
    )


def insert_album(conn, *, id, uuid, current_path=None, expected_path=None, title=None):
    conn.execute(
        """
        INSERT INTO album (id, uuid, title, current_path, expected_path)
        VALUES (?, ?, ?, ?, ?)
        """,
        (id, uuid, title, current_path, expected_path),
    )


def insert_workspace(
    conn,
    *,
    id,
    album_id=None,
    belongs_to_album_id=None,
    current_path="dummy/path",
    primary_model="Model",
    studio_name="Studio",
    album_name="Album",
):
    conn.execute(
        """
        INSERT INTO workspace_album
            (id, current_path, primary_model, studio_name, album_name, album_id, belongs_to_album_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (id, current_path, primary_model, studio_name, album_name, album_id, belongs_to_album_id),
    )


# ---------------------------------------------------------------------------
# Tests: Path-column migration
# ---------------------------------------------------------------------------

class TestPathMigration(unittest.TestCase):

    def setUp(self):
        self.conn = make_conn()
        create_v01_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run_migration(self, force_path=None):
        stats = MigrationStats()
        migrate_album_table(self.conn, stats, force_path)
        return stats

    def _get_paths(self):
        return {
            r["id"]: r["path"]
            for r in self.conn.execute("SELECT id, path FROM album").fetchall()
        }

    def test_equal_paths(self):
        """Both paths equal → path = that value."""
        insert_album(
            self.conn, id=1, uuid="u1",
            current_path="A/B/album", expected_path="A/B/album",
        )
        self._run_migration()
        paths = self._get_paths()
        self.assertEqual(paths[1], "A/B/album")

    def test_only_current_path(self):
        """Only current_path set → path = current_path."""
        insert_album(
            self.conn, id=2, uuid="u2",
            current_path="A/B/album", expected_path=None,
        )
        self._run_migration()
        self.assertEqual(self._get_paths()[2], "A/B/album")

    def test_only_expected_path(self):
        """Only expected_path set → path = expected_path."""
        insert_album(
            self.conn, id=3, uuid="u3",
            current_path=None, expected_path="A/B/album",
        )
        self._run_migration()
        self.assertEqual(self._get_paths()[3], "A/B/album")

    def test_both_null(self):
        """Both paths null → path = null."""
        insert_album(
            self.conn, id=4, uuid="u4",
            current_path=None, expected_path=None,
        )
        self._run_migration()
        self.assertIsNone(self._get_paths()[4])

    def test_conflicting_paths_raises(self):
        """Conflicting paths without --force-path → ConflictError."""
        insert_album(
            self.conn, id=5, uuid="u5",
            current_path="A/B/lower", expected_path="A/B/Upper",
        )
        with self.assertRaises(ConflictError):
            self._run_migration(force_path=None)

    def test_force_current_path(self):
        """Conflicting paths with --force-path=current → path = current_path."""
        insert_album(
            self.conn, id=6, uuid="u6",
            current_path="A/B/lower", expected_path="A/B/Upper",
        )
        self._run_migration(force_path="current")
        self.assertEqual(self._get_paths()[6], "A/B/lower")

    def test_force_expected_path(self):
        """Conflicting paths with --force-path=expected → path = expected_path."""
        insert_album(
            self.conn, id=7, uuid="u7",
            current_path="A/B/lower", expected_path="A/B/Upper",
        )
        self._run_migration(force_path="expected")
        self.assertEqual(self._get_paths()[7], "A/B/Upper")

    def test_removes_old_columns(self):
        """After migration, album must not have current_path or expected_path."""
        insert_album(self.conn, id=8, uuid="u8", current_path="x", expected_path="x")
        self._run_migration()
        cols = get_columns(self.conn, "album")
        self.assertNotIn("current_path", cols)
        self.assertNotIn("expected_path", cols)
        self.assertIn("path", cols)

    def test_all_other_columns_preserved(self):
        """Migration must not drop unrelated columns."""
        self.conn.execute(
            """
            INSERT INTO album (
                id, uuid, title, description, scene, location,
                capture_date, publish_date, rating,
                current_path, expected_path, created_at, updated_at
            ) VALUES (9, 'u9', 'T', 'D', 'S', 'L', '2024-01-01', '2024-02-01', 5,
                      'p', 'p', '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')
            """
        )
        self._run_migration()
        row = self.conn.execute("SELECT * FROM album WHERE id = 9").fetchone()
        self.assertEqual(row["title"], "T")
        self.assertEqual(row["description"], "D")
        self.assertEqual(row["scene"], "S")
        self.assertEqual(row["location"], "L")
        self.assertEqual(row["rating"], 5)
        self.assertEqual(row["path"], "p")


# ---------------------------------------------------------------------------
# Tests: Album-relation migration
# ---------------------------------------------------------------------------

class TestAlbumRelationMigration(unittest.TestCase):

    def setUp(self):
        self.conn = make_conn()
        create_v01_schema(self.conn)
        self.conn.execute("DROP TABLE album")
        create_album_v02(self.conn)
        create_album_relation_table(self.conn)
        # Insert some permanent albums
        for aid, uuid in [(1, "a1"), (2, "a2"), (3, "a3"), (4, "a4")]:
            self.conn.execute(
                "INSERT INTO album (id, uuid, path) VALUES (?, ?, ?)",
                (aid, uuid, f"path/{uuid}"),
            )

    def tearDown(self):
        self.conn.close()

    def _run_relation_migration(self):
        stats = MigrationStats()
        migrate_album_relations(self.conn, stats)
        return stats

    def _get_relations(self):
        rows = self.conn.execute(
            "SELECT album_id, related_album_id, relation_type FROM album_relation ORDER BY album_id"
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def test_null_belongs_to_skipped(self):
        """workspace_album rows with null belongs_to_album_id are skipped."""
        insert_workspace(self.conn, id=10, album_id=1, belongs_to_album_id=None)
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_skipped_null, 1)
        self.assertEqual(self._get_relations(), [])

    def test_self_belongs_to_skipped(self):
        """workspace_album rows where belongs_to_album_id == id are skipped."""
        insert_workspace(self.conn, id=11, album_id=2, belongs_to_album_id=11)
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_skipped_self, 1)
        self.assertEqual(self._get_relations(), [])

    def test_valid_cross_relation_inserted(self):
        """Valid non-self relation creates album_relation row."""
        insert_workspace(self.conn, id=20, album_id=1, belongs_to_album_id=21)
        insert_workspace(self.conn, id=21, album_id=2, belongs_to_album_id=21)
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_inserted, 1)
        relations = self._get_relations()
        self.assertIn((1, 2, "BELONGS_TO"), relations)

    def test_permanent_self_relation_skipped(self):
        """If both workspace rows resolve to same permanent album → skipped."""
        # Two workspace rows pointing to same permanent album
        insert_workspace(self.conn, id=30, album_id=3, belongs_to_album_id=31)
        insert_workspace(self.conn, id=31, album_id=3, belongs_to_album_id=31)  # same perm album
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_skipped_perm_self, 1)
        self.assertEqual(self._get_relations(), [])

    def test_missing_target_workspace_reported(self):
        """If target workspace row doesn't exist → skipped and reported as invalid."""
        insert_workspace(self.conn, id=40, album_id=1, belongs_to_album_id=999)
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_skipped_invalid, 1)
        self.assertEqual(len(stats.skipped_invalid_list), 1)
        self.assertEqual(stats.skipped_invalid_list[0].ws_id, 40)
        self.assertEqual(self._get_relations(), [])

    def test_missing_target_album_id_reported(self):
        """If target workspace row has null album_id → skipped and reported."""
        insert_workspace(self.conn, id=50, album_id=1, belongs_to_album_id=51)
        insert_workspace(self.conn, id=51, album_id=None, belongs_to_album_id=51)  # null album_id
        stats = self._run_relation_migration()
        self.assertEqual(stats.relations_skipped_invalid, 1)
        self.assertEqual(self._get_relations(), [])

    def test_idempotent_rerun(self):
        """Rerunning migration inserts no duplicates."""
        insert_workspace(self.conn, id=60, album_id=1, belongs_to_album_id=61)
        insert_workspace(self.conn, id=61, album_id=2, belongs_to_album_id=61)
        self._run_relation_migration()
        # Run again
        stats2 = self._run_relation_migration()
        # Second run: INSERT OR IGNORE means 0 new rows, no error
        self.assertEqual(stats2.relations_inserted, 0)
        relations = self._get_relations()
        self.assertEqual(len(relations), 1)
        self.assertIn((1, 2, "BELONGS_TO"), relations)

    def test_no_self_relations_in_output(self):
        """album_relation must never have rows where album_id == related_album_id."""
        # Two workspace rows resolving to same perm album → must be skipped
        insert_workspace(self.conn, id=70, album_id=4, belongs_to_album_id=71)
        insert_workspace(self.conn, id=71, album_id=4, belongs_to_album_id=71)
        self._run_relation_migration()
        self_count = self.conn.execute(
            "SELECT COUNT(*) FROM album_relation WHERE album_id = related_album_id"
        ).fetchone()[0]
        self.assertEqual(self_count, 0)


# ---------------------------------------------------------------------------
# Tests: Full migration pipeline (end-to-end)
# ---------------------------------------------------------------------------

class TestFullMigration(unittest.TestCase):

    def setUp(self):
        self.conn = make_conn()
        create_v01_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def _run_full(self, force_path=None):
        stats = MigrationStats()
        migrate_album_table(self.conn, stats, force_path)
        create_album_relation_table(self.conn)
        migrate_album_relations(self.conn, stats)
        return stats

    def test_full_pipeline_idempotent(self):
        """Running full migration twice must be safe and idempotent."""
        insert_album(self.conn, id=1, uuid="u1", current_path="P/a", expected_path="P/a")
        insert_workspace(self.conn, id=1, album_id=1, belongs_to_album_id=1)  # self → skipped

        stats1 = self._run_full()
        # After first run, album table now has 'path' not 'current_path'.
        # Second run: migrate_album_table sees 'path' already, no current_path → no-op rebuild.
        # But we need to re-run from a fresh perspective; simulate by calling again.
        stats2 = MigrationStats()
        # On second run: album already rebuilt, so same function should handle gracefully.
        migrate_album_table(self.conn, stats2, force_path=None)
        create_album_relation_table(self.conn)  # IF NOT EXISTS → no-op
        migrate_album_relations(self.conn, stats2)

        # No duplicate relations
        count = self.conn.execute("SELECT COUNT(*) FROM album_relation").fetchone()[0]
        self.assertEqual(count, 0)

    def test_verify_passes_after_clean_migration(self):
        """verify() returns no warnings after a clean migration."""
        insert_album(self.conn, id=1, uuid="u1", current_path="P/a", expected_path="P/a")
        insert_workspace(self.conn, id=1, album_id=1, belongs_to_album_id=1)

        self._run_full()
        self.conn.execute("PRAGMA foreign_keys = ON")
        warnings = verify(self.conn)
        self.assertEqual(warnings, [])

    def test_workspace_album_columns_unchanged(self):
        """workspace_album retains current_path, expected_path, belongs_to_album_id."""
        self._run_full()
        wa_cols = get_columns(self.conn, "workspace_album")
        for col in ("current_path", "expected_path", "belongs_to_album_id"):
            self.assertIn(col, wa_cols)


if __name__ == "__main__":
    unittest.main()
