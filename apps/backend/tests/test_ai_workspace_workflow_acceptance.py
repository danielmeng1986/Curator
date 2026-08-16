"""BT-053 disposable Album AI Workspace workflow acceptance."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from apps.backend import repositories as repo
from apps.backend import services as svc
from apps.backend.tests.workflow_support import WorkflowSandbox


VISION={"scene":"A family walking beside a lake","people":{"minimum":3,"maximum":4},
    "location_environment":"Outdoor lakeside","subjects":["family"],"objects":["trees"],
    "actions":["walking"],"confidence":0.91,"warnings":[]}
WRITER_A={"album_summary":"A calm family outing","description":"A family explores a lakeside setting.",
    "suggested_names":["Lakeside Family Walk","Quiet Summer Shore","Morning By The Lake",
        "Family Waterside Adventure","Gentle Lakeside Memories","Together Near The Water"]}
WRITER_B={"album_summary":"A bright walk near water","description":"A second model describes the same evidence.",
    "suggested_names":["Golden Lakeside Journey","Summer Water Memories","Family Morning Adventure",
        "Walking Beside Water","Bright Shore Together","Peaceful Family Escape"]}


class Fixture:
    def __init__(self,sandbox,config_count=2):
        self.s=sandbox; self.db=sandbox.db_factory(); self.now=datetime(2026,8,10,tzinfo=timezone.utc)
        with self.db() as conn:
            conn.execute("INSERT INTO status(name) VALUES ('TEMPORARY')"); conn.execute("INSERT INTO status(name) VALUES ('NAME_GENERATED')")
            conn.execute("""INSERT INTO album(uuid,status_id,title,path,created_at,updated_at)
                VALUES ('fixture-album',1,'Uncurated Album','album-fixture','now','album-v1')"""); self.album_id=conn.execute("SELECT last_insert_rowid()").fetchone()[0]; conn.commit()
        self.album_dir=sandbox.archive_root/"album-fixture"; self.album_dir.mkdir()
        for index in range(10):
            (self.album_dir/f"fixture-{index:02d}.jpg").write_bytes(b"\xff\xd8\xff"+bytes([index])*(1000+index*100))
        self.workspace_repo=repo.AIWorkspaceRepository(self.db); self.workspace_service=svc.AIWorkspaceService(self.workspace_repo,now_fn=lambda:self.now)
        self.workspace=self.workspace_service.create("Disposable AI Acceptance","admin-token")
        self.config_service=svc.AIModelConfigurationService(repo.AIModelConfigurationRepository(self.db))
        self.configs=[]
        for index in range(config_count):
            self.configs.append(self.config_service.create({"name":f"Fixture Config {index+1}","model_identifier":f"mock-{index+1}",
                "model_file":f"mock-{index+1}.gguf","vision_prompt_version":"v1","writer_prompt_version":"w1",
                "sample_count":8,"context_size":4096,"threads":4,"gpu_layers":0,"max_tokens":800,
                "temperature":0.2+index/10,"image_max_tokens":384}))
        self.dispatch_repo=repo.AlbumAIWorkDispatchRepository(self.db)
        self.dispatch=svc.WorkDispatchService(self.dispatch_repo,repo.AlbumRepository(self.db),
            workspace_repo=self.workspace_repo,configuration_service=self.config_service,
            preview_secret=b"bt053-dispatch",now_fn=lambda:self.now)
        preview=self.dispatch.preview("album_name_analysis",self.workspace["uuid"],[c["uuid"] for c in self.configs],
            album_ids=[self.album_id],created_by_token_uuid="admin-token")
        self.dispatch_result=self.dispatch.execute(preview["preview_token"],"admin-token")
        self.group_uuid=self.dispatch_result["groups"][0]["group_uuid"]
        self.item_uuids=self.dispatch_result["groups"][0]["work_item_uuids"]
        self.item_repo=repo.AIWorkItemRepository(self.db)
        self.items=svc.AIWorkItemService(self.item_repo,self.workspace_repo,repo.AlbumRepository(self.db),self.config_service,now_fn=lambda:self.now)
        self.evidence=svc.AIPhotoEvidenceManifestService(repo.AIPhotoEvidenceRepository(self.db),self.item_repo,
            repo.AlbumRepository(self.db),sandbox.archive_root,repo.IssueRepository(self.db),now_fn=lambda:self.now)
        self.results=svc.AIResultSubmissionService(repo.AIResultRepository(self.db),self.evidence,now_fn=lambda:self.now)
        self.reviews=svc.AIReviewService(repo.AIReviewRepository(self.db),now_fn=lambda:self.now)
        self.promotions=svc.AIAlbumNamePromotionService(repo.AIAlbumNamePromotionRepository(self.db),
            repo.StatusRepository(self.db),b"bt053-promotion",now_fn=lambda:self.now)

    def run_worker(self,item_uuid,token,writer):
        manifest=self.evidence.create(item_uuid); claimed=self.items.claim_next(token,300)
        if claimed["uuid"]!=item_uuid: raise AssertionError("Fixture queue order changed.")
        transferred=[]
        for evidence in manifest["evidence"]:
            meta=self.evidence.metadata(evidence["uuid"],"writer",token)
            descriptor=self.evidence.content_descriptor(evidence["uuid"],"writer",token)
            transferred.append({"uuid":meta["uuid"],"sha256":meta["sha256"],"bytes":descriptor["path"].read_bytes()})
        self.results.submit(item_uuid,token,"Vision",self.results.VISION_SCHEMA,VISION,{"provider":"mock_llama_cpp"})
        self.results.submit(item_uuid,token,"Writer",self.results.WRITER_SCHEMA,writer,{"provider":"mock_llama_cpp"})
        return manifest,transferred


class TestAIWorkspaceWorkflowAcceptance(unittest.TestCase):
    class OtherWorker:
        worker_kind="metadata_enrichment"; dataset_type="album_metadata"; schema_version=1
        item_kind="metadata_work_item"
        def eligibility(self,album,context=None):
            return {"can_dispatch":bool(album),"eligibility":"ELIGIBLE","reason":None,"warnings":[]}

    def test_multi_configuration_happy_path_unique_winner_release_archive_and_redispatch(self):
        with WorkflowSandbox() as sandbox:
            f=Fixture(sandbox,2)
            self.assertEqual(1,len(f.dispatch_result["groups"])); self.assertEqual(2,len(f.item_uuids))
            with f.db() as conn:
                self.assertEqual("TEMPORARY",conn.execute("SELECT s.name FROM album a JOIN status s ON s.id=a.status_id WHERE a.id=?",(f.album_id,)).fetchone()[0])
                self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM workspace_album").fetchone()[0])
            manifests=[]
            for index,item_uuid in enumerate(f.item_uuids):
                manifest,transferred=f.run_worker(item_uuid,f"writer-{index+1}",WRITER_A if index==0 else WRITER_B)
                manifests.append(manifest); self.assertEqual(8,len(transferred))
                self.assertTrue(all(blob["bytes"].startswith(b"\xff\xd8\xff") for blob in transferred))
                self.assertNotIn(str(sandbox.archive_root),json.dumps(manifest))
                f.reviews.start(item_uuid,1,"admin-token")
                with self.assertRaises(svc.ServiceConflict) as stale:
                    f.reviews.start(item_uuid,1,"admin-token")
                self.assertEqual("AI_REVIEW_STALE",stale.exception.code)
                chosen=(WRITER_A if index==0 else WRITER_B)["suggested_names"][0]
                f.reviews.decide(item_uuid,2,"approve","admin-token",{"rating":5-index,
                    "selection_source":"Recommendation","selected_name":chosen})
            first=f.promotions.preview(f.item_uuids[0],"admin-token")
            promoted=f.promotions.execute(first["preview_token"],True,"admin-token")
            self.assertTrue(f.promotions.execute(first["preview_token"],True,"admin-token")["idempotent"])
            second=f.promotions.preview(f.item_uuids[1],"admin-token")
            with self.assertRaises(svc.ServiceConflict) as conflict:
                f.promotions.execute(second["preview_token"],True,"admin-token")
            self.assertEqual("AI_PROMOTION_WINNER_EXISTS",conflict.exception.code)
            detail=f.dispatch.group_detail(f.group_uuid); self.assertIn("release",detail["allowed_actions"])
            f.dispatch.close_group(f.group_uuid,1,"release","Winner promoted","admin-token")
            closed=f.workspace_service.close(f.workspace["uuid"],1,"All Groups released","admin-token")
            archived=f.workspace_service.archive(f.workspace["uuid"],2,"Indefinite audit history","admin-token")
            self.assertEqual("Completed",closed["retention"]["outcome_classification"]); self.assertEqual("Archived",archived["lifecycle_state"])
            with f.db() as conn:
                album=conn.execute("SELECT a.title,s.name status_name FROM album a JOIN status s ON s.id=a.status_id WHERE a.id=?",(f.album_id,)).fetchone()
                self.assertEqual("Lakeside Family Walk",album["title"]); self.assertEqual("NAME_GENERATED",album["status_name"])
                self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM workspace_album_name_promotion WHERE outcome='Promoted'").fetchone()[0])
                self.assertEqual(2,conn.execute("SELECT COUNT(*) FROM ai_work_item_review WHERE state='Approved'").fetchone()[0])
                self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM album_work_reservation").fetchone()[0])
                self.assertEqual(promoted["uuid"],conn.execute("SELECT uuid FROM workspace_album_name_promotion WHERE outcome='Promoted'").fetchone()[0])
            # Archived Workspace is immutable; redispatch must use a new Open Workspace and identities.
            new_workspace=f.workspace_service.create("Redispatch Workspace","admin-token")
            preview=f.dispatch.preview("album_name_analysis",new_workspace["uuid"],[f.configs[0]["uuid"]],album_ids=[f.album_id],created_by_token_uuid="admin-token")
            redispatched=f.dispatch.execute(preview["preview_token"],"admin-token")
            self.assertNotEqual(f.group_uuid,redispatched["groups"][0]["group_uuid"])
            self.assertNotEqual(f.item_uuids[0],redispatched["groups"][0]["work_item_uuids"][0])

    def test_hash_change_wrong_claim_and_schema_fail_without_false_success(self):
        with WorkflowSandbox() as sandbox:
            f=Fixture(sandbox,1); item=f.item_uuids[0]; manifest=f.evidence.create(item)
            claimed=f.items.claim_next("writer-owner",300); self.assertEqual(item,claimed["uuid"])
            with self.assertRaises(svc.AuthorizationFailure): f.evidence.metadata(manifest["evidence"][0]["uuid"],"writer","writer-other")
            with self.assertRaises(ValueError): f.results.submit(item,"writer-owner","Vision","unsupported-schema",VISION)
            changed=f.album_dir/manifest["evidence"][0]["relative_path"]; changed.write_bytes(changed.read_bytes()+b"changed")
            with self.assertRaises(svc.ServiceConflict) as conflict:
                f.results.submit(item,"writer-owner","Vision",f.results.VISION_SCHEMA,VISION)
            self.assertEqual("EVIDENCE_CONTENT_CHANGED",conflict.exception.code)
            with f.db() as conn:
                exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_work_item_result_stage'").fetchone()
                self.assertFalse(exists and conn.execute("SELECT COUNT(*) FROM ai_work_item_result_stage").fetchone()[0])
            f.items.fail(item,"writer-owner","EVIDENCE_CHANGED","Fixture evidence changed")
            f.dispatch.close_group(f.group_uuid,1,"abandon","Evidence fixture intentionally changed","admin-token")
            closed=f.workspace_service.close(f.workspace["uuid"],1,"Abandoned changed evidence","admin-token")
            self.assertEqual("Abandoned",closed["retention"]["outcome_classification"])
            history=f.evidence.historical(item); self.assertEqual(1,history["availability_counts"]["Changed"])

    def test_cross_worker_reservation_conflict_is_zero_write(self):
        with WorkflowSandbox() as sandbox:
            f=Fixture(sandbox,1)
            registry=svc.WorkDispatchAdapterRegistry((svc.AlbumNameAnalysisDispatchAdapter(),self.OtherWorker()))
            other=svc.WorkDispatchService(repo.WorkDispatchRepository(f.db),repo.AlbumRepository(f.db),registry,now_fn=lambda:f.now)
            batch=other.create_batch("metadata_enrichment")
            with self.assertRaises(svc.ServiceConflict) as conflict: other.reserve_album(batch["uuid"],f.album_id)
            self.assertEqual("ALBUM_ALREADY_RESERVED",conflict.exception.code)
            with f.db() as conn:
                self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM album_work_reservation WHERE album_id=?",(f.album_id,)).fetchone()[0])
                self.assertEqual(1,conn.execute("SELECT COUNT(*) FROM work_dispatch_group WHERE album_id=?",(f.album_id,)).fetchone()[0])

    def test_rework_successor_is_auditable_and_rejected_without_album_mutation(self):
        with WorkflowSandbox() as sandbox:
            f=Fixture(sandbox,1); original=f.item_uuids[0]; f.run_worker(original,"writer-one",WRITER_A)
            f.reviews.start(original,1,"admin-token")
            reworked=f.reviews.decide(original,2,"request_rework","admin-token",{"rating":2,"reason":"Need a clearer summary"})
            successor=reworked["successor_work_item_uuid"]; self.assertNotEqual(original,successor)
            f.run_worker(successor,"writer-two",WRITER_B); f.reviews.start(successor,1,"admin-token")
            f.reviews.decide(successor,2,"reject","admin-token",{"rating":1,"reason":"Recommendations remain unsuitable"})
            self.assertIn("release",f.dispatch.group_detail(f.group_uuid)["allowed_actions"])
            f.dispatch.close_group(f.group_uuid,1,"release","Rework rejected","admin-token")
            closed=f.workspace_service.close(f.workspace["uuid"],1,"Rejected after rework","admin-token")
            self.assertEqual("Mixed",closed["retention"]["outcome_classification"])
            with f.db() as conn:
                self.assertEqual("Uncurated Album",conn.execute("SELECT title FROM album WHERE id=?",(f.album_id,)).fetchone()[0])
                self.assertEqual(0,conn.execute("SELECT COUNT(*) FROM workspace_album_name_promotion WHERE outcome='Promoted'").fetchone()[0])
                link=conn.execute("SELECT * FROM ai_work_item_rework WHERE successor_work_item_uuid=?",(successor,)).fetchone()
                self.assertEqual(original,link["rework_of_work_item_uuid"])
