import unittest
import json
import hashlib
import io
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from workers.ai_worker.client import CuratorClient,EnrollmentClient,CuratorApiError
from workers.ai_worker.workflow import AnalysisWorkflow,validate_writer_payload
from workers.ai_worker.provider import LlamaCliProvider,LlamaTextCliProvider,ProviderError,parse_json_object,validate_mtmd_cli,validate_text_cli
from workers.ai_worker.runtime import WorkerRuntime
from workers.ai_worker.cli import parser
from workers.ai_worker import config
class FakeProvider:
    def __init__(self, failures=0): self.failures=failures
    def complete(self, prompt):
        if self.failures: self.failures-=1; raise ProviderError("x")
        return '{"suggested_names": []}'
class WorkerTests(unittest.TestCase):
    def test_run_requires_a_registered_worker_kind(self):
        with self.assertRaises(SystemExit):parser().parse_args(["run","--llama-cli","llama","--model-root","models"])
        args=parser().parse_args(["run","--worker-kind","album_name_analysis","--llama-cli","llama-mtmd-cli","--text-cli","llama-cli","--model-root","models","--once"])
        self.assertEqual("album_name_analysis",args.worker_kind);self.assertTrue(args.once)

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
        client.claim_work("album_name_analysis",120,30);client.heartbeat("item-1",120);client.fail_work("item-1","MODEL_TIMEOUT","timeout")
        self.assertEqual(["/api/v1/ai-work-items/claim", "/api/v1/ai-work-items/item-1/heartbeat", "/api/v1/ai-work-items/item-1/fail"],
                         [request.full_url.replace("http://curator", "") for request in requests])
        self.assertTrue(all(request.headers["Authorization"] == "Bearer writer-token" for request in requests))
        self.assertEqual({"worker_kinds":["album_name_analysis"],"lease_seconds":120,"wait_seconds":30},json.loads(requests[0].data))
        self.assertEqual("MODEL_TIMEOUT", json.loads(requests[2].data)["error_code"])

    def test_api_client_reports_backend_error_code_and_message(self):
        body=b'{"error":{"code":"REQUEST_INVALID","message":"suggested_names must contain exactly six unique names."}}'
        def opener(request,timeout):raise HTTPError(request.full_url,400,"Bad Request",{},io.BytesIO(body))
        with self.assertRaises(CuratorApiError) as raised:CuratorClient("http://curator","writer-token",opener=opener).submit_writer("item-1",{})
        self.assertEqual(400,raised.exception.status);self.assertEqual("REQUEST_INVALID",raised.exception.code)
        self.assertIn("suggested_names must contain",str(raised.exception));self.assertIn("HTTP 400",str(raised.exception))

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
            def claim_work(self,*_):return {"data":{"item":{"uuid":"item-1","worker_kind":"album_name_analysis","configuration_snapshot":{}}}}
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

    def test_runtime_rejects_and_truthfully_fails_a_mismatched_claim_before_evidence(self):
        class Client:
            def __init__(self):self.calls=[]
            def fail_work(self,*args):self.calls.append(args)
        client=Client();claimed={"uuid":"item-1","worker_kind":"other_kind","configuration_snapshot":{}}
        with self.assertRaisesRegex(RuntimeError,"does not match"):
            WorkerRuntime(client,object(),worker_kind="album_name_analysis").run_once(claimed)
        self.assertEqual("WORKER_KIND_MISMATCH",client.calls[0][1])

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
        self.assertNotIn("--no-display-prompt",args)
        self.assertTrue(run.call_args.kwargs["check"]);self.assertNotIn("shell",run.call_args.kwargs)

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_llama_provider_reports_bounded_redacted_stderr_and_category(self,run):
        error=subprocess.CalledProcessError(1,["llama-mtmd-cli"],stderr="unknown argument --bad /private/model.gguf curator-ai-worker-secret/evidence-1.jpg")
        run.side_effect=error
        with self.assertRaises(ProviderError) as raised:
            LlamaCliProvider("llama-mtmd-cli","/private/model.gguf").complete("private prompt",images=[Path("curator-ai-worker-secret/evidence-1.jpg")])
        self.assertEqual("MODEL_PROVIDER_ARGUMENT_INVALID",raised.exception.error_code)
        self.assertNotIn("/private/model.gguf",str(raised.exception));self.assertNotIn("evidence-1.jpg",str(raised.exception))
        self.assertLessEqual(len(str(raised.exception)),1000)

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_llama_provider_reports_timeout(self,run):
        run.side_effect=subprocess.TimeoutExpired(["llama-mtmd-cli"],1)
        with self.assertRaises(ProviderError) as raised:LlamaCliProvider("llama-mtmd-cli","model.gguf",timeout_seconds=1).complete("inspect")
        self.assertEqual("MODEL_PROVIDER_TIMEOUT",raised.exception.error_code)

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_mtmd_preflight_requires_multimodal_options(self,run):
        run.return_value.stdout="--mmproj --image --image-max-tokens --gpu-layers";run.return_value.stderr=""
        validate_mtmd_cli("llama-mtmd-cli")
        run.return_value.stdout="--image"
        with self.assertRaisesRegex(ProviderError,"missing required options"):validate_mtmd_cli("llama-mtmd-cli")

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_text_provider_is_single_turn_and_non_interactive(self,run):
        run.return_value.stdout='```json\n{"status":"ok"}\n```';run.return_value.stderr=""
        payload,_=LlamaTextCliProvider("llama-cli","model.gguf").complete("write",settings={"max_tokens":128},json_schema={"type":"object"})
        args=run.call_args.args[0]
        self.assertEqual({"status":"ok"},payload)
        for option in ("--single-turn","--simple-io","--no-display-prompt","--no-show-timings"):self.assertIn(option,args)
        self.assertIn("--json-schema",args)
        self.assertNotIn("--mmproj",args);self.assertNotIn("--image",args)

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_text_preflight_requires_single_turn_options(self,run):
        run.return_value.stdout="--single-turn --simple-io --no-display-prompt --no-show-timings --json-schema --gpu-layers";run.return_value.stderr=""
        validate_text_cli("llama-cli")
        run.return_value.stdout="--gpu-layers"
        with self.assertRaisesRegex(ProviderError,"missing required options"):validate_text_cli("llama-cli")

    def test_analysis_routes_images_only_to_vision_provider(self):
        class Provider:
            def __init__(self,result):self.result,self.calls=result,[]
            def complete(self,prompt,**kwargs):self.calls.append((prompt,kwargs));return self.result,{"duration_ms":1}
        valid={"album_summary":"Garden scene","description":"A garden setting.","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Reverie","Golden Afternoon","Gentle Elegance","Serene Moments"]}
        vision=Provider({"scene":"garden"});writer=Provider(valid)
        workflow=AnalysisWorkflow(vision,writer)
        vision_result,_=workflow.vision([Path("one.jpg")],{"max_tokens":128})
        workflow.writer(vision_result,{"max_tokens":128})
        self.assertEqual([Path("one.jpg")],vision.calls[0][1]["images"])
        self.assertNotIn("images",writer.calls[0][1])

    def test_writer_validation_retries_with_feedback_before_submission(self):
        valid={"album_summary":"Garden scene","description":"A garden setting.","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Reverie","Golden Afternoon","Gentle Elegance","Serene Moments"]}
        class Provider:
            def __init__(self):self.calls=[]
            def complete(self,prompt,**kwargs):
                self.calls.append((prompt,kwargs))
                return ({"album_summary":"bad","description":"bad","suggested_names":["gallery"]} if len(self.calls)==1 else valid),{"duration_ms":1}
        provider=Provider();payload,_=AnalysisWorkflow(object(),provider,sleep=lambda _:None).writer({"scene":"garden"},{})
        self.assertEqual(valid,payload);self.assertEqual(2,len(provider.calls));self.assertIn("failed validation",provider.calls[1][0])
        self.assertIn("json_schema",provider.calls[0][1])

    def test_writer_validation_matches_backend_name_rules(self):
        base={"album_summary":"Summary","description":"Description","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Reverie","Golden Afternoon","Gentle Elegance","Serene Moments"]}
        self.assertEqual(base,validate_writer_payload(base))
        for names in (["Only One"],base["suggested_names"][:-1]+["lowercase name"],base["suggested_names"][:-1]+["Private Photo"]):
            with self.assertRaises(ProviderError):validate_writer_payload({**base,"suggested_names":names})

    def test_runtime_preserves_provider_failure_category(self):
        class Client:
            def __init__(self):self.failure=None
            def prepare_manifest(self,*_):raise ProviderError("safe failure",error_code="MODEL_PROVIDER_CONTEXT_FAILED")
            def heartbeat(self,*_):pass
            def fail_work(self,*args):self.failure=args
        client=Client();claimed={"uuid":"item-1","worker_kind":"album_name_analysis","configuration_snapshot":{}}
        with self.assertRaises(ProviderError):WorkerRuntime(client,object()).run_once(claimed)
        self.assertEqual("MODEL_PROVIDER_CONTEXT_FAILED",client.failure[1])
