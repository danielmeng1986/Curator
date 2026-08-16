"""MT-007 migration safety and album.remark compatibility tests."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from apps.backend.migrations.runner import MIGRATION_ID, migrate


class AlbumRemarkMigrationTests(unittest.TestCase):
    def _pre_migration_database(self, root: Path) -> Path:
        database = root / "pre-migration.db"
        with closing(sqlite3.connect(database)) as conn, conn:
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
            with closing(sqlite3.connect(database)) as conn, conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(album)")}
                row = conn.execute("SELECT id, uuid, title, path, status_id, remark FROM album WHERE id = 7").fetchone()
                versions = [row[0] for row in conn.execute(
                    "SELECT migration_id FROM schema_migration ORDER BY migration_id"
                )]
                self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
            self.assertIn("remark", columns)
            self.assertEqual((7, "album-7", "Existing Album", "A/Existing", 42, None), row)
            self.assertIn(MIGRATION_ID, versions)
            self.assertEqual("0000_base_catalog", versions[0])
            self.assertEqual("0021_natural_writer_titles", versions[-1])

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
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.execute("ALTER TABLE album ADD COLUMN remark TEXT")
                conn.execute("UPDATE album SET remark = 'kept' WHERE id = 7")
            result = migrate(database, root / "backups")
            self.assertTrue(result.applied)
            self.assertTrue(result.adopted_existing_column)
            with closing(sqlite3.connect(database)) as conn, conn:
                self.assertEqual("kept", conn.execute("SELECT remark FROM album WHERE id = 7").fetchone()[0])


class AIWorkspaceContainerMigrationTests(unittest.TestCase):
    def test_0003_is_repeatable_and_keeps_container_and_item_state_separate(self):
        sql = (Path(__file__).parents[1] / "migrations" / "0003_ai_workspace_container.sql").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "workspace.db"
            with closing(sqlite3.connect(database)) as conn, conn:
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
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.executescript(sql); conn.executescript(sql)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(ai_model_configuration)")}
        self.assertIn("context_size", columns); self.assertIn("model_file", columns)
        self.assertNotIn("cli_path", columns); self.assertNotIn("model_path", columns)

    def test_0005_work_item_attempt_history_is_separate_from_current_state(self):
        root = Path(__file__).parents[1] / "migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON"); conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            conn.executescript((root / "0003_ai_workspace_container.sql").read_text())
            conn.executescript((root / "0004_ai_model_configuration.sql").read_text())
            conn.executescript((root / "0005_album_ai_work_item.sql").read_text()); conn.executescript((root / "0005_album_ai_work_item.sql").read_text())
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("workspace_album_ai_worker", tables); self.assertIn("ai_work_item_attempt", tables)

    def test_0016_backfills_worker_kind_and_adds_attempt_capability_snapshot(self):
        root=Path(__file__).parents[1]/"migrations"
        with closing(sqlite3.connect(":memory:")) as conn,conn:
            conn.execute("PRAGMA foreign_keys=ON");conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            for name in ("0003_ai_workspace_container.sql","0004_ai_model_configuration.sql","0005_album_ai_work_item.sql"):
                conn.executescript((root/name).read_text())
            conn.execute("INSERT INTO album VALUES (1)")
            conn.execute("INSERT INTO ai_dataset_schema VALUES ('album_analysis',1,'Active','{}','n')")
            conn.execute("INSERT INTO ai_workspace(uuid,dataset_type,schema_version,title,created_at) VALUES ('w','album_analysis',1,'w','n')")
            conn.execute("INSERT INTO ai_model_configuration(uuid,name,provider_type,model_identifier,model_file,vision_prompt_version,writer_prompt_version,sample_count,context_size,threads,gpu_layers,max_tokens,temperature,image_max_tokens,additional_parameters_json,enabled,version,created_at,updated_at) VALUES ('c','c','llama_cpp','m','f','v','w',8,512,1,0,1,0,1,'{}',1,1,'n','n')")
            conn.execute("INSERT INTO workspace_album_ai_worker(uuid,workspace_uuid,album_id,ai_model_configuration_uuid,configuration_snapshot_json,created_at,updated_at) VALUES ('i','w',1,'c','{}','n','n')")
            conn.executescript((root/"0016_capability_aware_work_claim.sql").read_text())
            row=conn.execute("SELECT worker_kind FROM workspace_album_ai_worker WHERE uuid='i'").fetchone()
            attempt_columns={column[1] for column in conn.execute("PRAGMA table_info(ai_work_item_attempt)")}
        self.assertEqual(("album_name_analysis",),row);self.assertIn("worker_kinds_json",attempt_columns)

    def test_0006_dispatch_is_repeatable_and_reservation_is_album_unique(self):
        root = Path(__file__).parents[1] / "migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
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

    def test_0007_preview_claim_is_repeatable_and_single_use(self):
        root = Path(__file__).parents[1] / "migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            conn.executescript((root / "0006_work_dispatch_foundation.sql").read_text())
            sql = (root / "0007_work_dispatch_execution.sql").read_text()
            conn.executescript(sql); conn.executescript(sql)
            conn.execute("""INSERT INTO work_dispatch_batch
                (uuid,worker_kind,dataset_type,schema_version,created_at,updated_at)
                VALUES ('batch','album_name_analysis','album_analysis',1,'now','now')""")
            conn.execute("INSERT INTO work_dispatch_preview_claim VALUES ('preview','batch','admin','now')")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO work_dispatch_preview_claim VALUES ('preview','batch-2','admin','now')")

    def test_0008_evidence_manifest_is_repeatable_and_item_unique(self):
        root = Path(__file__).parents[1] / "migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON"); conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            for name in ("0003_ai_workspace_container.sql","0004_ai_model_configuration.sql","0005_album_ai_work_item.sql"):
                conn.executescript((root / name).read_text())
            sql = (root / "0008_ai_photo_evidence_manifest.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(ai_photo_evidence_manifest)")}
        self.assertIn("workspace_album_ai_worker_photo",tables); self.assertTrue(indexes)

    def test_0009_two_stage_results_are_repeatable_and_stage_unique(self):
        root = Path(__file__).parents[1] / "migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON"); conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            for name in ("0003_ai_workspace_container.sql","0004_ai_model_configuration.sql",
                         "0005_album_ai_work_item.sql","0008_ai_photo_evidence_manifest.sql"):
                conn.executescript((root / name).read_text())
            sql = (root / "0009_two_stage_ai_results.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            conn.execute("INSERT INTO album(id) VALUES (1)")
            conn.execute("INSERT INTO ai_dataset_schema VALUES ('album_analysis',1,'Active','{}','n')")
            conn.execute("INSERT INTO ai_workspace(uuid,dataset_type,schema_version,title,lifecycle_state,version,created_at) VALUES ('w','album_analysis',1,'w','Open',1,'n')")
            conn.execute("INSERT INTO ai_model_configuration(uuid,name,provider_type,model_identifier,model_file,vision_prompt_version,writer_prompt_version,sample_count,context_size,threads,gpu_layers,max_tokens,temperature,image_max_tokens,additional_parameters_json,enabled,version,created_at,updated_at) VALUES ('c','c','llama_cpp','m','f','v','w',8,1,1,1,1,0.1,1,'{}',1,1,'n','n')")
            conn.execute("INSERT INTO workspace_album_ai_worker(uuid,workspace_uuid,album_id,ai_model_configuration_uuid,configuration_snapshot_json,run_state,version,created_at,updated_at) VALUES ('i','w',1,'c','{}','Pending',1,'n','n')")
            conn.execute("INSERT INTO ai_photo_evidence_manifest(uuid,work_item_uuid,album_id,manifest_version,sample_count,eligible_image_count,average_size_bytes,selection_method,discovery_summary_json,selected_at) VALUES ('m','i',1,1,8,8,1,'x','{}','n')")
            values = ("r","i","Vision","v","m",1,"h","{}","p","{}","o","t","n")
            conn.execute("INSERT INTO ai_work_item_result_stage(uuid,work_item_uuid,stage,schema_version,manifest_uuid,manifest_version,configuration_snapshot_sha256,payload_json,payload_sha256,runtime_metrics_json,operation_uuid,submitted_by_token_uuid,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",values)
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO ai_work_item_result_stage(uuid,work_item_uuid,stage,schema_version,manifest_uuid,manifest_version,configuration_snapshot_sha256,payload_json,payload_sha256,runtime_metrics_json,operation_uuid,submitted_by_token_uuid,submitted_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",("r2",)+values[1:])

    def test_0010_review_schema_is_repeatable_and_preserves_rework_lineage(self):
        root=Path(__file__).parents[1]/"migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE workspace_album_ai_worker(uuid TEXT PRIMARY KEY)")
            sql=(root/"0010_ai_work_item_review.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            tables={row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"ai_work_item_review","ai_work_item_review_decision","ai_work_item_rework"}<=tables)

    def test_0011_promotion_schema_is_repeatable_and_has_single_winner_index(self):
        root=Path(__file__).parents[1]/"migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE ai_workspace(uuid TEXT PRIMARY KEY)")
            conn.execute("CREATE TABLE workspace_album_ai_worker(uuid TEXT PRIMARY KEY)")
            conn.execute("CREATE TABLE album(id INTEGER PRIMARY KEY)")
            sql=(root/"0011_ai_album_name_promotion.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            indexes=conn.execute("PRAGMA index_list(workspace_album_name_promotion)").fetchall()
        self.assertTrue(any(row[2] for row in indexes))

    def test_0012_group_closure_schema_is_repeatable(self):
        root=Path(__file__).parents[1]/"migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE work_dispatch_group(uuid TEXT PRIMARY KEY)")
            sql=(root/"0012_work_dispatch_group_closure.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            columns={row[1] for row in conn.execute("PRAGMA table_info(work_dispatch_group_closure)")}
        self.assertTrue({"group_uuid","disposition","operation_uuid","summary_json"}<=columns)

    def test_0013_workspace_retention_schema_is_repeatable(self):
        root=Path(__file__).parents[1]/"migrations"
        with closing(sqlite3.connect(":memory:")) as conn, conn:
            conn.execute("CREATE TABLE ai_workspace(uuid TEXT PRIMARY KEY)")
            sql=(root/"0013_ai_workspace_retention.sql").read_text(); conn.executescript(sql); conn.executescript(sql)
            columns={row[1] for row in conn.execute("PRAGMA table_info(ai_workspace_retention)")}
        self.assertTrue({"retention_classification","outcome_classification","archive_reason"}<=columns)


class CanonicalOrderedMigrationTests(unittest.TestCase):
    def test_empty_database_builds_complete_current_schema_in_order(self):
        expected = {
            "album", "photo", "device_registration", "operation", "repair_case",
            "quarantine_item", "ai_workspace", "workspace_album_ai_worker",
            "work_dispatch_batch", "ai_photo_evidence_manifest",
            "ai_work_item_review", "workspace_album_name_promotion",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); database = root / "empty.db"
            result = migrate(database, root / "backups")
            with closing(sqlite3.connect(database)) as conn, conn:
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
                versions = [row[0] for row in conn.execute(
                    "SELECT migration_id FROM schema_migration ORDER BY migration_id"
                )]
                self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
                self.assertEqual("ok", conn.execute("PRAGMA integrity_check").fetchone()[0])
            self.assertTrue(expected <= tables)
            self.assertEqual(22, len(versions))
            self.assertEqual(tuple(versions), result.applied_migrations)
            self.assertTrue(result.backup and result.backup.is_file())

    def test_partial_upgrade_applies_only_missing_tail_then_replays_without_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); database = root / "partial.db"
            migrate(database, root / "backups")
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.execute("DROP TABLE ai_workspace_retention")
                conn.execute("DELETE FROM schema_migration WHERE migration_id='0013_ai_workspace_retention'")
                conn.execute("DROP TABLE admin_bootstrap_code")
                conn.execute("DELETE FROM schema_migration WHERE migration_id='0014_authentication_and_operations'")
            resumed = migrate(database, root / "backups")
            replay = migrate(database, root / "backups")
            self.assertEqual(
                ("0013_ai_workspace_retention", "0014_authentication_and_operations"),
                resumed.applied_migrations,
            )
            self.assertFalse(replay.applied); self.assertIsNone(replay.backup)
            self.assertEqual(2, len(list((root / "backups").glob("*.db"))))

    def test_unrecorded_0015_and_0016_adopt_existing_defensive_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);database=root/"adopt.db";migrate(database,root/"backups")
            with closing(sqlite3.connect(database)) as conn,conn:
                conn.execute("DELETE FROM schema_migration WHERE migration_id IN ('0015_ui_device_enrollment','0016_capability_aware_work_claim')")
            result=migrate(database,root/"backups")
            with closing(sqlite3.connect(database)) as conn:
                recorded={row[0] for row in conn.execute("SELECT migration_id FROM schema_migration")}
                registration={row[1] for row in conn.execute("PRAGMA table_info(device_registration)")}
                work_items={row[1] for row in conn.execute("PRAGMA table_info(workspace_album_ai_worker)")}
                attempts={row[1] for row in conn.execute("PRAGMA table_info(ai_work_item_attempt)")}
            self.assertEqual(("0015_ui_device_enrollment","0016_capability_aware_work_claim"),result.applied_migrations)
            self.assertTrue({"candidate_token_hash","enrollment_proof_hash","enrollment_expires_at","cancelled_at"}<=registration)
            self.assertIn("worker_kind",work_items);self.assertIn("worker_kinds_json",attempts)
            self.assertTrue({"0015_ui_device_enrollment","0016_capability_aware_work_claim"}<=recorded)

    def test_active_historical_workspace_requires_guarded_mt008_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); database = root / "legacy.db"
            with closing(sqlite3.connect(database)) as conn, conn:
                conn.executescript((Path(__file__).parents[1] / "migrations" / "0000_base_catalog.sql").read_text())
                conn.execute("INSERT INTO workspace_album(studio_name) VALUES ('legacy')")
            with self.assertRaisesRegex(Exception, "MT-008"):
                migrate(database, root / "backups")
            with closing(sqlite3.connect(database)) as conn, conn:
                self.assertFalse(conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_workspace'"
                ).fetchone())
                self.assertFalse(conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migration'"
                ).fetchone())
