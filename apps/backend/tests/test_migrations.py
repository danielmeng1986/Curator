"""MT-007 migration safety and album.remark compatibility tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apps.backend.migrations.runner import MIGRATION_ID, migrate


class AlbumRemarkMigrationTests(unittest.TestCase):
    def _pre_migration_database(self, root: Path) -> Path:
        database = root / "pre-migration.db"
        with sqlite3.connect(database) as conn:
            conn.executescript(
                """CREATE TABLE album (
                    id INTEGER PRIMARY KEY,
                    uuid TEXT NOT NULL UNIQUE,
                    title TEXT,
                    path TEXT,
                    status_id INTEGER
                );
                CREATE TABLE album_model (id INTEGER PRIMARY KEY, album_id INTEGER REFERENCES album(id));
                INSERT INTO album (id, uuid, title, path, status_id)
                    VALUES (7, 'album-7', 'Existing Album', 'A/Existing', 42);"""
            )
        return database

    def test_adds_nullable_remark_and_preserves_existing_album_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = self._pre_migration_database(root)
            result = migrate(database, root / "backups")
            self.assertTrue(result.applied)
            self.assertTrue(result.backup and result.backup.is_file())
            with sqlite3.connect(database) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(album)")}
                row = conn.execute("SELECT id, uuid, title, path, status_id, remark FROM album WHERE id = 7").fetchone()
                version = conn.execute("SELECT migration_id FROM schema_migration").fetchone()[0]
                self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
            self.assertIn("remark", columns)
            self.assertEqual((7, "album-7", "Existing Album", "A/Existing", 42, None), row)
            self.assertEqual(MIGRATION_ID, version)

    def test_rerun_is_a_no_op_without_a_second_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = self._pre_migration_database(root)
            first = migrate(database, root / "backups")
            second = migrate(database, root / "backups")
            self.assertTrue(first.applied)
            self.assertFalse(second.applied)
            self.assertIsNone(second.backup)
            self.assertEqual(1, len(list((root / "backups").glob("*.db"))))

    def test_existing_unrecorded_column_is_adopted_without_losing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            database = self._pre_migration_database(root)
            with sqlite3.connect(database) as conn:
                conn.execute("ALTER TABLE album ADD COLUMN remark TEXT")
                conn.execute("UPDATE album SET remark = 'kept' WHERE id = 7")
            result = migrate(database, root / "backups")
            self.assertTrue(result.applied)
            self.assertTrue(result.adopted_existing_column)
            with sqlite3.connect(database) as conn:
                self.assertEqual("kept", conn.execute("SELECT remark FROM album WHERE id = 7").fetchone()[0])

