from __future__ import annotations

import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from apps.backend import repositories as repo
from apps.backend import services as svc
from apps.backend.translation import DeepLTranslationAdapter, TranslationConfigurationError, load_translation_config
from apps.backend import server as server_module


class _Response:
    def __init__(self, payload): self._body=io.BytesIO(json.dumps(payload).encode())
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self._body.read(size)


class TranslationConfigurationTests(unittest.TestCase):
    def test_env_file_loads_without_overriding_process_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/".env"; path.write_text("CURATOR_DEEPL_API_KEY=file-key\nCURATOR_DEEPL_API_PLAN=developer\n")
            os.chmod(path,0o600)
            result=load_translation_config(Path(tmp),{"CURATOR_DEEPL_API_KEY":"process-key"})
            self.assertEqual("process-key",result["api_key"]); self.assertEqual("developer",result["plan"])

    def test_unsafe_mode_and_shell_syntax_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/".env"; path.write_text("CURATOR_DEEPL_API_KEY=$(unsafe)\n"); os.chmod(path,0o644)
            with self.assertRaises(TranslationConfigurationError): load_translation_config(Path(tmp),{})
            os.chmod(path,0o600)
            with self.assertRaises(TranslationConfigurationError): load_translation_config(Path(tmp),{})


class DeepLAdapterTests(unittest.TestCase):
    def test_batches_json_and_returns_bounded_results_without_exposing_key(self):
        seen={}
        def opener(req,timeout):
            seen["url"],seen["timeout"],seen["body"]=req.full_url,timeout,json.loads(req.data)
            return _Response({"translations":[{"text":"空灵倒影","detected_source_language":"EN"}]})
        result=DeepLTranslationAdapter("secret-test-key",opener=opener).translate(["Ethereal Reflection"])
        self.assertEqual("空灵倒影",result[0]["text"]); self.assertIn("api-free.deepl.com",seen["url"])
        self.assertNotIn("secret-test-key",json.dumps(seen))


class TranslationServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:"); self.db.row_factory=sqlite3.Row
        self.db.execute("CREATE TABLE ai_work_item_result_stage(work_item_uuid TEXT,stage TEXT,payload_json TEXT)")
        self.db.execute("INSERT INTO ai_work_item_result_stage VALUES (?,?,?)",("item-1","Writer",
            json.dumps({"suggested_names":["Ethereal Reflection","Mirror Whisper","Ethereal Reflection"]})))
        self.repository=repo.AIReviewTranslationRepository(lambda:self.db)

    def tearDown(self): self.db.close()

    def test_first_request_translates_unique_misses_and_replay_is_cache_only(self):
        class FakeAdapter:
            calls=[]
            def translate(inner,texts,target):
                inner.calls.append((list(texts),target)); return [{"text":"中:"+text,"detected_source_language":"EN"} for text in texts]
        adapter=FakeAdapter(); service=svc.AIReviewTranslationService(self.repository,adapter)
        first=service.translate("item-1","admin"); second=service.translate("item-1","admin")
        self.assertEqual(2,first["cached_count"]); self.assertEqual(0,second["missing_count"])
        self.assertEqual([(["Ethereal Reflection","Mirror Whisper"],"ZH-HANS")],adapter.calls)
        original=json.loads(self.db.execute("SELECT payload_json FROM ai_work_item_result_stage").fetchone()[0])
        self.assertEqual("Ethereal Reflection",original["suggested_names"][0])

    def test_missing_configuration_is_readable_but_translate_is_blocked(self):
        service=svc.AIReviewTranslationService(self.repository)
        self.assertFalse(service.read("item-1")["configured"])
        with self.assertRaises(svc.ServiceConflict) as caught: service.translate("item-1","admin")
        self.assertEqual("TRANSLATION_NOT_CONFIGURED",caught.exception.code)


class TranslationHttpContractTests(unittest.TestCase):
    def test_admin_get_and_post_use_translation_boundary(self):
        calls=[]
        class FakeService:
            def read(self,item_uuid): calls.append(("read",item_uuid)); return {"work_item_uuid":item_uuid,"configured":True}
            def translate(self,item_uuid,actor): calls.append(("translate",item_uuid,actor)); return {"work_item_uuid":item_uuid,"cached_count":2}
        fake=FakeService()
        class Handler(server_module.AppHandler):
            def _authorize_versioned_api(self,path,method):
                self._principal={"role":"admin","token_uuid":"admin-1"}; return True
            def _ai_review_translation_service(self): return fake
            def log_message(self,*args): pass
        httpd=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True); thread.start()
        try:
            connection=HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
            connection.request("GET","/api/v1/ai-work-items/item-1/review-translations")
            response=connection.getresponse(); body=json.loads(response.read()); connection.close()
            self.assertEqual(200,response.status); self.assertEqual("item-1",body["data"]["translations"]["work_item_uuid"])
            connection=HTTPConnection("127.0.0.1",httpd.server_port,timeout=5)
            connection.request("POST","/api/v1/ai-work-items/item-1/review-translations",body=b"{}",
                headers={"Content-Type":"application/json"})
            response=connection.getresponse(); body=json.loads(response.read()); connection.close()
            self.assertEqual(200,response.status); self.assertEqual(2,body["data"]["translations"]["cached_count"])
            self.assertEqual([("read","item-1"),("translate","item-1","admin-1")],calls)
        finally:
            httpd.shutdown(); httpd.server_close(); thread.join()


if __name__ == "__main__": unittest.main()
