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


class AIWorkspaceContainerMigrationTests(unittest.TestCase):
    def test_0003_is_repeatable_and_keeps_container_and_item_state_separate(self):
        sql = (Path(__file__).parents[1] / "migrations" / "0003_ai_workspace_container.sql").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "workspace.db"
            with sqlite3.connect(database) as conn:
                conn.execute("PRAGMA foreign_keys=ON"); conn.executescript(sql); conn.executescript(sql)
                conn.execute("INSERT INTO ai_dataset_schema VALUES ('album_analysis',1,'Active','{}','2026-08-09')")
                conn.execute("""INSERT INTO ai_workspace
                    (uuid,dataset_type,schema_version,title,created_at)
                    VALUES ('workspace-1','album_analysis',1,'Comparison','2026-08-09')""")
                row = conn.execute("SELECT dataset_type,schema_version,lifecycle_state,version FROM ai_workspace").fetchone()
                self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual(("album_analysis", 1, "Open", 1), row)

    def test_0004_model_configuration_is_repeatable_and_has_no_host_path_column(self):
        sql = (Path(__file__).parents[1] / "migrations" / "0004_ai_model_configuration.sql").read_text()
        with sqlite3.connect(":memory:") as conn:
            conn.executescript(sql); conn.executescript(sql)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_model_configuration)")}
        self.assertIn("context_size", columns); self.assertIn("model_file", columns)
        self.assertNotIn("cli_path", columns); self.assertNotIn("model_path", columns)

    def test_0005_work_item_attempt_history_is_separate_from_current_state(self):
        root = Path(__file__).parents[1] / "migrations"
        with sqlite3.connect(":memory:") as conn:
            conn.execute("PRAGMA foreign_keys=ON"); conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            conn.executescript((root / "0003_ai_workspace_container.sql").read_text())
            conn.executescript((root / "0004_ai_model_configuration.sql").read_text())
            conn.executescript((root / "0005_album_ai_work_item.sql").read_text()); conn.executescript((root / "0005_album_ai_work_item.sql").read_text())
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("workspace_album_ai_worker", tables); self.assertIn("ai_work_item_attempt", tables)

    def test_0006_dispatch_is_repeatable_and_reservation_is_album_unique(self):
        root = Path(__file__).parents[1] / "migrations"
        with sqlite3.connect(":memory:") as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            sql = (root / "0006_work_dispatch_foundation.sql").read_text()
            conn.executescript(sql); conn.executescript(sql)
            conn.execute("INSERT INTO album VALUES (1)")
            conn.execute("""INSERT INTO work_dispatch_batch
                (uuid,worker_kind,dataset_type,schema_version,created_at,updated_at)
                VALUES ('b1','album_name_analysis','album_analysis',1,'now','now')""")
            conn.execute("""INSERT INTO work_dispatch_group
                (uuid,batch_uuid,album_id,worker_kind,dataset_type,schema_version,created_at,updated_at)
                VALUES ('g1','b1',1,'album_name_analysis','album_analysis',1,'now','now')""")
            conn.execute("INSERT INTO album_work_reservation VALUES (1,'g1','b1','album_name_analysis','now')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO album_work_reservation VALUES (1,'g2','b1','other_worker','now')")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("work_dispatch_batch", tables)
        self.assertIn("work_dispatch_group", tables)
        self.assertIn("work_dispatch_group_item", tables)
