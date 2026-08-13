import unittest
import json
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch
from workers.ai_worker.client import CuratorClient,EnrollmentClient
from workers.ai_worker.workflow import AnalysisWorkflow
from workers.ai_worker.provider import LlamaCliProvider,ProviderError,parse_json_object
from workers.ai_worker.runtime import WorkerRuntime
from workers.ai_worker import config
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

    def test_headless_enrollment_hashes_candidate_and_never_sends_plaintext(self):
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self):return b'{"data":{"registration":{"uuid":"registration-1"}}}'
        def opener(request,timeout):requests.append(request);return Response()
        EnrollmentClient("http://curator",opener=opener).request(device_name="WSL Worker",device_identity="device-1",
            registration_proof="proof",token="candidate-secret",enrollment_proof="enrollment-secret-value-long")
        body=json.loads(requests[0].data);self.assertEqual(hashlib.sha256(b"candidate-secret").hexdigest(),body["candidate_token_hash"])
        self.assertNotIn("candidate-secret",requests[0].data.decode());self.assertEqual("writer",body["requested_role"])

    def test_private_state_round_trip_and_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"state.json";config.save({"token":"secret"},path)
            self.assertEqual("secret",config.load(path)["token"]);self.assertEqual(0,path.stat().st_mode & 0o077)

    def test_runtime_downloads_validates_submits_and_cleans(self):
        image=b"\xff\xd8\xfffixture";digest=hashlib.sha256(image).hexdigest()
        class Client:
            def __init__(self):self.calls=[]
            def claim_work(self,*_):return {"data":{"item":{"uuid":"item-1","configuration_snapshot":{}}}}
            def prepare_manifest(self,item):return {"data":{"manifest":{"evidence":[{"uuid":"e-1","ordinal":1,"size_bytes":len(image),"sha256":digest,"mime_type":"image/jpeg"}]}}}
            def download_evidence(self,*_):return image
            def submit_vision(self,*args):self.calls.append(("vision",args))
            def submit_writer(self,*args):self.calls.append(("writer",args))
            def heartbeat(self,*_):pass
            def fail_work(self,*_):self.calls.append(("fail",()))
        class Workflow:
            def vision(self,paths,settings):self.paths=list(paths);return {"scene":"fixture"},{"duration_ms":1}
            def writer(self,vision,settings):return {"suggested_names":["a"]},{"duration_ms":1}
        client=Client();workflow=Workflow();self.assertEqual("item-1",WorkerRuntime(client,workflow).run_once())
        self.assertEqual(["vision","writer"],[item[0] for item in client.calls]);self.assertFalse(workflow.paths[0].exists())

    def test_json_extraction_ignores_provider_noise(self):
        self.assertEqual({"scene":"lake"},parse_json_object("timing log\n{\"scene\":\"lake\"}\nmore"))

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_llama_provider_passes_bounded_multimodal_configuration(self,run):
        run.return_value.stdout='{"scene":"lake"}'
        payload,metrics=LlamaCliProvider("llama-mtmd-cli","model.gguf",mmproj="mmproj.gguf").complete(
            "inspect",images=[Path("one.jpg"),Path("two.jpg")],settings={"image_max_tokens":256})
        args=run.call_args.args[0]
        self.assertEqual({"scene":"lake"},payload);self.assertEqual("llama_cpp",metrics["provider"])
        self.assertEqual("one.jpg,two.jpg",args[args.index("--image")+1])
        self.assertEqual("256",args[args.index("--image-max-tokens")+1])
        self.assertEqual("mmproj.gguf",args[args.index("--mmproj")+1])
        self.assertTrue(run.call_args.kwargs["check"]);self.assertNotIn("shell",run.call_args.kwargs)
