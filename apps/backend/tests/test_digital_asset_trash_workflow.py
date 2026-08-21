"""BT-034 recoverable Album Trash workflow acceptance."""
import sqlite3
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from apps.backend import repositories as repo
from apps.backend import services as svc
from apps.backend.migrations.runner import migrate


class DigitalAssetTrashWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="curator-trash-")
        self.root=Path(self.temp.name); self.database=self.root/"Curator.db"
        self.archive=self.root/"archive"; self.trash=self.root/"trash"
        self.archive.mkdir(); self.trash.mkdir()
        migrate(self.database,self.root/"backups")
        def factory():
            connection=sqlite3.connect(self.database); connection.row_factory=sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON"); return connection
        self.factory=factory; self.albums=repo.AlbumRepository(factory)
        self.operations=svc.OperationService(repo.OperationRepository(factory))
        self.service=svc.DigitalAssetTrashService(self.albums,self.operations,self.archive,self.trash,
            b"bt034-trash",now_fn=lambda:datetime(2026,8,20,tzinfo=timezone.utc))
        with factory() as connection:
            connection.execute("""INSERT INTO album(uuid,title,path,created_at,updated_at)
                VALUES ('album-trash','Three Photos','Studio/Three Photos','2026-08-20','2026-08-20')""")
            for ordinal in range(3):
                connection.execute("INSERT INTO photo(uuid,album_id,filename,relative_path,created_at) VALUES (?,?,?,?,?)",
                    (f"photo-{ordinal}",1,f"{ordinal}.jpg",f"{ordinal}.jpg","2026-08-20"))
            connection.commit()
        directory=self.archive/"Studio"/"Three Photos"; directory.mkdir(parents=True)
        for ordinal in range(3): (directory/f"{ordinal}.jpg").write_bytes(f"photo-{ordinal}".encode())

    def tearDown(self): self.temp.cleanup()

    def test_trash_hides_album_preserves_rows_and_restore_returns_same_identity(self):
        preview=self.service.preview_trash(1,"writer-token")
        self.assertEqual(3,preview["photo_count"])
        self.assertEqual("Studio/Three Photos",preview["path"])
        self.assertEqual("2026-09-19T00:00:00+00:00",preview["retention_until"])
        result=self.service.execute_trash(preview["preview_token"],"writer-token")
        current=self.service.list()
        self.assertEqual([result["trash_uuid"]],[item["uuid"] for item in current])
        self.assertTrue(current[0]["can_restore"])
        self.assertEqual(["restore","hold"],current[0]["allowed_actions"])
        self.assertFalse((self.archive/"Studio"/"Three Photos").exists())
        self.assertEqual([],self.albums.search()[0])
        with self.factory() as connection:
            album=connection.execute("SELECT uuid,status_id,catalog_state,asset_state FROM album WHERE id=1").fetchone()
            self.assertEqual(("album-trash",None,"TRASHED","TRASHED"),tuple(album))
            self.assertEqual(3,connection.execute("SELECT COUNT(*) FROM photo WHERE album_id=1").fetchone()[0])
        restore=self.service.preview_restore(result["trash_uuid"],"admin-token")
        restored=self.service.execute_restore(restore["preview_token"],"admin-token")
        self.assertEqual("ACTIVE",restored["catalog_state"])
        self.assertTrue((self.archive/"Studio"/"Three Photos"/"0.jpg").exists())
        self.assertEqual("album-trash",self.albums.get_by_id(1)["album"]["uuid"])
        self.assertEqual([],self.service.list())
        history=self.service.list(include_restored=True)
        self.assertEqual(1,len(history)); self.assertFalse(history[0]["can_restore"])
        self.assertEqual([],history[0]["allowed_actions"])

    def test_hold_blocks_restore_preview_until_released(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        item=self.service.get(result["trash_uuid"])
        held=self.service.set_hold(item["uuid"],item["lifecycle_version"],"Preserve evidence","admin")["item"]
        self.assertFalse(held["can_restore"])
        self.assertEqual(["release_hold"],held["allowed_actions"])
        self.assertEqual("LIFECYCLE_HELD",held["restore_blockers"][0]["code"])
        with self.assertRaisesRegex(svc.ServiceConflict,"lifecycle hold"):
            self.service.preview_restore(item["uuid"],"admin")
        released=self.service.set_hold(item["uuid"],held["lifecycle_version"],None,"admin")["item"]
        self.assertTrue(released["can_restore"])

    def test_active_reservation_blocks_preview_without_filesystem_change(self):
        with self.factory() as connection:
            connection.execute("INSERT INTO work_dispatch_batch(uuid,worker_kind,dataset_type,schema_version,batch_state,created_at,updated_at) VALUES ('b','kind','data',1,'Active','n','n')")
            connection.execute("INSERT INTO work_dispatch_group(uuid,batch_uuid,album_id,worker_kind,dataset_type,schema_version,group_state,created_at,updated_at) VALUES ('g','b',1,'kind','data',1,'Active','n','n')")
            connection.execute("INSERT INTO album_work_reservation(album_id,group_uuid,batch_uuid,worker_kind,reserved_at) VALUES (1,'g','b','kind','n')")
            connection.commit()
        preview=self.service.preview_trash(1,"writer-token")
        self.assertFalse(preview["can_trash"]); self.assertIsNone(preview["preview_token"])
        self.assertIn("ACTIVE_WORK_RESERVATION",{item["code"] for item in preview["blockers"]})
        self.assertTrue((self.archive/"Studio"/"Three Photos").exists())

    def test_admin_hold_and_release_preserve_recoverable_assets(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        item=self.service.get(result["trash_uuid"])
        held=self.service.set_hold(item["uuid"],item["lifecycle_version"],"Preserve evidence","admin")
        self.assertEqual("Preserve evidence",held["item"]["hold_reason"])
        released=self.service.set_hold(item["uuid"],held["item"]["lifecycle_version"],None,"admin")
        self.assertIsNone(released["item"]["hold_reason"])
        self.assertTrue((self.trash/item["trash_relative_path"]).exists())

    def test_expired_unheld_assets_are_purged_but_database_evidence_remains(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        with self.factory() as connection:
            connection.execute("UPDATE digital_asset_trash_item SET retention_until='2026-08-19T00:00:00+00:00'")
            connection.commit()
        item=self.service.get(result["trash_uuid"])
        self.assertTrue(item["can_purge"]); self.assertIn("purge",item["allowed_actions"])
        preview=self.service.preview_purge(item["uuid"],"admin")
        purged=self.service.execute_purge(preview["preview_token"],"admin")
        self.assertEqual("DELETED",purged["asset_state"]); self.assertFalse(purged["assets_available"])
        self.assertFalse((self.trash/item["trash_relative_path"]).exists())
        replay=self.service.execute_purge(preview["preview_token"],"admin")
        self.assertTrue(replay["replayed"]); self.assertEqual(purged["operation_uuid"],replay["operation_uuid"])
        with self.factory() as connection:
            album=connection.execute("SELECT status_id,catalog_state,asset_state FROM album WHERE id=1").fetchone()
            self.assertEqual((None,"TRASHED","DELETED"),tuple(album))
            self.assertEqual(3,connection.execute("SELECT COUNT(*) FROM photo WHERE album_id=1").fetchone()[0])
            evidence=connection.execute("SELECT purged_at,purge_photo_count,purge_byte_count,purge_inventory_digest FROM digital_asset_trash_item").fetchone()
            self.assertTrue(evidence[0]); self.assertEqual(3,evidence[1]); self.assertGreater(evidence[2],0); self.assertTrue(evidence[3])

    def test_retention_and_hold_block_purge_without_asset_mutation(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        item=self.service.get(result["trash_uuid"])
        self.assertFalse(item["can_purge"])
        self.assertEqual("ASSET_RETENTION_ACTIVE",item["purge_blockers"][-1]["code"])
        with self.assertRaisesRegex(svc.ServiceConflict,"retention period"):
            self.service.preview_purge(item["uuid"],"admin")
        with self.factory() as connection:
            connection.execute("UPDATE digital_asset_trash_item SET retention_until='2026-08-19T00:00:00+00:00'")
            connection.commit()
        current=self.service.get(item["uuid"])
        held=self.service.set_hold(item["uuid"],current["lifecycle_version"],"Legal evidence","admin")["item"]
        with self.assertRaisesRegex(svc.ServiceConflict,"hold"):
            self.service.preview_purge(item["uuid"],"admin")
        self.assertTrue((self.trash/item["trash_relative_path"]).exists())

    def test_reviewed_batch_purge_reports_scope_and_replays_durable_outcome(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        with self.factory() as connection:
            connection.execute("UPDATE digital_asset_trash_item SET retention_until='2026-08-19T00:00:00+00:00'")
            connection.commit()
        preview=self.service.preview_purge_batch([result["trash_uuid"]],"admin")
        self.assertEqual({"requested":1,"eligible":1,"excluded":0,"photo_count":3,"byte_count":21},preview["summary"])
        executed=self.service.execute_purge_batch(preview["preview_token"],"admin")
        self.assertEqual({"total":1,"succeeded":1,"failed":0},executed["summary"])
        replay=self.service.execute_purge_batch(preview["preview_token"],"admin")
        self.assertTrue(replay["replayed"]); self.assertEqual(executed["operation_uuid"],replay["operation_uuid"])

    def test_missing_scope_after_preview_is_truthfully_recorded(self):
        result=self.service.execute_trash(self.service.preview_trash(1,"writer")["preview_token"],"writer")
        with self.factory() as connection:
            connection.execute("UPDATE digital_asset_trash_item SET retention_until='2026-08-19T00:00:00+00:00'"); connection.commit()
        item=self.service.get(result["trash_uuid"]); preview=self.service.preview_purge(item["uuid"],"admin")
        shutil.rmtree(self.trash/item["trash_relative_path"])
        with self.assertRaisesRegex(svc.ServiceConflict,"missing"):
            self.service.execute_purge(preview["preview_token"],"admin")
        with self.factory() as connection:
            self.assertEqual("MISSING",connection.execute("SELECT asset_state FROM album WHERE id=1").fetchone()[0])


if __name__ == "__main__": unittest.main()
