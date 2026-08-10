import unittest
import json
from workers.ai_worker.client import CuratorClient
from workers.ai_worker.workflow import AnalysisWorkflow
from workers.ai_worker.provider import ProviderError
class FakeProvider:
    def __init__(self, failures=0): self.failures=failures
    def complete(self, prompt):
        if self.failures: self.failures-=1; raise ProviderError("x")
        return '{"suggested_names": []}'
class WorkerTests(unittest.TestCase):
    def test_result_is_suggestion_only_after_retry(self):
        result=AnalysisWorkflow(FakeProvider(1), sleep=lambda _: None).analyze("x")
        self.assertEqual("suggestion_only", result["status"]); self.assertEqual(2, result["attempt"])

    def test_worker_queue_calls_are_rest_only_and_bearer_authenticated(self):
        requests = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): pass
            def read(self): return b'{"data":{"item":null}}'
        def opener(request, timeout): requests.append(request); return Response()
        client = CuratorClient("http://curator", "writer-token", opener=opener)
        client.claim_work(120); client.heartbeat("item-1", 120); client.fail_work("item-1", "MODEL_TIMEOUT", "timeout")
        self.assertEqual(["/api/v1/ai-work-items/claim", "/api/v1/ai-work-items/item-1/heartbeat", "/api/v1/ai-work-items/item-1/fail"],
                         [request.full_url.replace("http://curator", "") for request in requests])
        self.assertTrue(all(request.headers["Authorization"] == "Bearer writer-token" for request in requests))
        self.assertEqual("MODEL_TIMEOUT", json.loads(requests[2].data)["error_code"])

    def test_worker_downloads_evidence_by_opaque_identity_only(self):
        requests = []
        class Response:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def read(self): return b"image-bytes"
        def opener(request,timeout): requests.append(request); return Response()
        content = CuratorClient("http://curator","writer-token",opener=opener).download_evidence("evidence-uuid")
        self.assertEqual(b"image-bytes",content)
        self.assertEqual("/api/v1/ai-evidence/evidence-uuid/content",requests[0].full_url.replace("http://curator",""))
        self.assertNotIn("path",requests[0].full_url)

    def test_worker_submits_versioned_vision_and_writer_results(self):
        requests=[]
        class Response:
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def read(self): return b'{"data":{"result":{}}}'
        def opener(request,timeout): requests.append(request); return Response()
        client=CuratorClient("http://curator","writer-token",opener=opener)
        client.submit_vision("item-1",{"scene":"lake"},{"duration_ms":2})
        client.submit_writer("item-1",{"suggested_names":[]})
        self.assertEqual(["/api/v1/ai-work-items/item-1/results/vision","/api/v1/ai-work-items/item-1/results/writer"],
            [request.full_url.replace("http://curator","") for request in requests])
        self.assertEqual("curator://album-analysis/vision/v1",json.loads(requests[0].data)["schema_version"])
