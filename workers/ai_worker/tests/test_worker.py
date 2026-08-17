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
from workers.ai_worker.provider import LlamaCliProvider,LlamaTextCliProvider,ProviderError,parse_json_object,parse_json_streams,validate_mtmd_cli,validate_text_cli
from workers.ai_worker.runtime import WorkerRuntime
from workers.ai_worker.cli import parser,run
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
        self.assertIsNone(args.model_debug_dir)
        self.assertEqual(3,args.max_consecutive_item_failures)

    def test_run_rejects_invalid_consecutive_failure_limit(self):
        args=parser().parse_args(["run","--worker-kind","album_name_analysis","--llama-cli","vision","--text-cli","writer",
            "--model-root","models","--max-consecutive-item-failures","0"])
        with patch("workers.ai_worker.cli.config.load",return_value={"status":"Approved"}):
            with self.assertRaisesRegex(ValueError,"max-consecutive-item-failures"):run(args)

    def test_run_skips_item_failures_resets_after_success_and_stops_at_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);vision=root/"vision";writer=root/"writer";model=root/"model.gguf"
            for path in (vision,writer,model):path.touch()
            args=parser().parse_args(["run","--worker-kind","album_name_analysis","--llama-cli",str(vision),
                "--text-cli",str(writer),"--model-root",str(root),"--max-consecutive-item-failures","3"])
            claims=[{"uuid":f"item-{index}","worker_kind":"album_name_analysis",
                "configuration_snapshot":{"model_file":"model.gguf"}} for index in range(1,6)]
            class Client:
                def principal(self):return {"data":{"principal":{"role":"writer"}}}
                def claim_work(self,*_):return {"data":{"item":claims.pop(0)}}
            runtime=unittest.mock.Mock()
            runtime.run_once.side_effect=[ProviderError("bad output",error_code="MODEL_OUTPUT_INVALID"),None,
                ProviderError("bad output",error_code="MODEL_OUTPUT_INVALID"),
                ProviderError("bad output",error_code="MODEL_OUTPUT_INVALID"),
                ProviderError("bad output",error_code="MODEL_OUTPUT_INVALID")]
            with patch("workers.ai_worker.cli.config.load",return_value={"status":"Approved","backend_url":"http://curator","token":"token"}), \
                    patch("workers.ai_worker.cli.validate_mtmd_cli"),patch("workers.ai_worker.cli.validate_text_cli"), \
                    patch("workers.ai_worker.cli.CuratorClient",return_value=Client()), \
                    patch("workers.ai_worker.cli.WorkerRuntime",return_value=runtime):
                with self.assertRaisesRegex(RuntimeError,"3 consecutive"):run(args)
            self.assertEqual(5,runtime.run_once.call_count)

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

    def test_json_extraction_checks_stderr_after_stdout(self):
        self.assertEqual({"scene":"lake"},parse_json_streams("ordinary stdout","log\n{\"scene\":\"lake\"}"))

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_opt_in_debug_log_records_both_streams_with_private_permissions(self,run):
        run.return_value.stdout="not json";run.return_value.stderr='log\n{"scene":"lake"}' ;run.return_value.returncode=0
        with tempfile.TemporaryDirectory() as root:
            debug=Path(root)/"item-1"
            payload,_=LlamaCliProvider("llama-mtmd-cli","model.gguf",debug_dir=debug).complete("inspect")
            self.assertEqual({"scene":"lake"},payload)
            files=list(debug.iterdir());self.assertEqual(3,len(files))
            self.assertEqual(0,debug.stat().st_mode & 0o077)
            self.assertTrue(all(path.stat().st_mode & 0o077==0 for path in files))
            self.assertEqual("not json",next(debug.glob("*.stdout.txt")).read_text())
            self.assertIn('{"scene":"lake"}',next(debug.glob("*.stderr.txt")).read_text())

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_llama_provider_passes_bounded_multimodal_configuration(self,run):
        run.return_value.stdout='{"scene":"lake"}'
        payload,metrics=LlamaCliProvider("llama-mtmd-cli","model.gguf",mmproj="mmproj.gguf").complete(
            "inspect",images=[Path("one.jpg"),Path("two.jpg")],settings={"image_max_tokens":256})
        args=run.call_args.args[0]
        self.assertEqual({"scene":"lake"},payload);self.assertEqual("llama_cpp",metrics["provider"])
        self.assertEqual(1,args.count("--image"))
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
        payload,metrics=LlamaTextCliProvider("llama-cli","model.gguf").complete("write",settings={"max_tokens":128})
        args=run.call_args.args[0]
        self.assertEqual({"status":"ok"},payload)
        for option in ("--single-turn","--simple-io","--no-display-prompt","--no-show-timings"):self.assertIn(option,args)
        self.assertIn("--grammar",args);self.assertIn("name2",args[args.index("--grammar")+1])
        self.assertEqual("writer-v1-gbnf-2-natural-titles",metrics["constrained_decoding"]);self.assertEqual(0,metrics["effective_temperature"])
        self.assertNotIn("--mmproj",args);self.assertNotIn("--image",args)

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_text_preflight_requires_single_turn_options(self,run):
        run.return_value.stdout="--single-turn --simple-io --no-display-prompt --no-show-timings --gpu-layers --grammar";run.return_value.stderr=""
        validate_text_cli("llama-cli")
        run.return_value.stdout="--gpu-layers"
        with self.assertRaisesRegex(ProviderError,"missing required options"):validate_text_cli("llama-cli")

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_writer_rejects_unreviewed_temperature_before_execution(self,run):
        with self.assertRaises(ProviderError) as raised:
            LlamaTextCliProvider("llama-cli","model.gguf").complete("write",settings={"writer_temperature":0.5})
        self.assertEqual("MODEL_PROVIDER_ARGUMENT_INVALID",raised.exception.error_code);run.assert_not_called()

    def test_writer_grammar_uses_gbnf_character_class_without_invalid_hyphen_escape(self):
        from workers.ai_worker.constraints import WRITER_GBNF
        self.assertIn("name-char ::= [A-Za-z'-]",WRITER_GBNF)
        self.assertIn("word ::= upper name-char{0,23}",WRITER_GBNF)
        self.assertNotIn(r"\-]",WRITER_GBNF)

    def test_analysis_routes_images_only_to_vision_provider(self):
        class Provider:
            def __init__(self,result):self.result,self.calls=result,[]
            def complete(self,prompt,**kwargs):self.calls.append((prompt,kwargs));return self.result,{"duration_ms":1}
        valid={"album_summary":"Garden scene","description":"A garden setting.","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Garden Light","Gentle Summer Elegance","Serene Moments By Water","Together Near The Garden"]}
        vision_payload={"scene":"garden","people":{"minimum":1,"maximum":1},
            "location_environment":"Outdoor garden","subjects":["person"],"objects":["bamboo"],
            "actions":["posing"],"confidence":0.9,"warnings":[]}
        vision=Provider(vision_payload);writer=Provider(valid)
        workflow=AnalysisWorkflow(vision,writer)
        vision_result,_=workflow.vision([Path("one.jpg")],{"max_tokens":128})
        workflow.writer(vision_result,{"max_tokens":128})
        self.assertEqual([Path("one.jpg")],vision.calls[0][1]["images"])
        self.assertNotIn("images",writer.calls[0][1])

    def test_vision_validation_retries_before_backend_submission(self):
        valid={"scene":"garden","people":{"minimum":1,"maximum":1},
            "location_environment":"Outdoor garden","subjects":["person"],"objects":["bamboo"],
            "actions":["posing"],"confidence":0.9,"warnings":[]}
        class Provider:
            def __init__(self):self.calls=[]
            def complete(self,prompt,**kwargs):
                self.calls.append((prompt,kwargs))
                return ({"scene":"garden"} if len(self.calls)==1 else valid),{"duration_ms":1}
        provider=Provider();payload,_=AnalysisWorkflow(provider,sleep=lambda _:None).vision([Path("one.jpg")],{})
        self.assertEqual(valid,payload);self.assertEqual(2,len(provider.calls))
        self.assertIn("failed validation",provider.calls[1][0])
        self.assertEqual([Path("one.jpg")],provider.calls[1][1]["images"])

    def test_vision_validation_matches_backend_v1_rules(self):
        from workers.ai_worker.workflow import validate_vision_payload
        valid={"scene":"garden","people":{"minimum":1,"maximum":2},
            "location_environment":"Outdoor garden","subjects":[],"objects":[],"actions":[],
            "confidence":0.8,"warnings":[]}
        self.assertEqual(valid,validate_vision_payload(valid))
        invalid=({**valid,"extra":True},{**valid,"people":{"minimum":2,"maximum":1}},
            {**valid,"confidence":True},{**valid,"subjects":"person"})
        for payload in invalid:
            with self.assertRaises(ProviderError):validate_vision_payload(payload)

    def test_writer_validation_retries_with_feedback_before_submission(self):
        valid={"album_summary":"Garden scene","description":"A garden setting.","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Garden Light","Gentle Summer Elegance","Serene Moments By Water","Together Near The Garden"]}
        class Provider:
            def __init__(self):self.calls=[]
            def complete(self,prompt,**kwargs):
                self.calls.append((prompt,kwargs))
                return ({"album_summary":"bad","description":"bad","suggested_names":["gallery"]} if len(self.calls)==1 else valid),{"duration_ms":1}
        provider=Provider();payload,_=AnalysisWorkflow(object(),provider,sleep=lambda _:None).writer({"scene":"garden"},{})
        self.assertEqual(valid,payload);self.assertEqual(2,len(provider.calls));self.assertIn("failed validation",provider.calls[1][0])
        self.assertNotIn("json_schema",provider.calls[0][1])

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_text_provider_detects_zero_exit_sampler_failure(self,run):
        run.return_value.stdout="Error: Failed to initialize samplers: std::exception";run.return_value.stderr="error initializing grammar sampler";run.return_value.returncode=0
        with self.assertRaises(ProviderError) as raised:LlamaTextCliProvider("llama-cli","model.gguf").complete("write")
        self.assertEqual("MODEL_PROVIDER_ARGUMENT_INVALID",raised.exception.error_code)
        self.assertIn("sampler",str(raised.exception))

    @patch("workers.ai_worker.provider.subprocess.run")
    def test_text_provider_classifies_grammar_parse_failure(self,run):
        run.side_effect=subprocess.CalledProcessError(-6,["llama-cli"],stderr="error parsing grammar: unknown escape; failed to parse grammar")
        with self.assertRaises(ProviderError) as raised:LlamaTextCliProvider("llama-cli","model.gguf").complete("write")
        self.assertEqual("MODEL_PROVIDER_ARGUMENT_INVALID",raised.exception.error_code)

    def test_writer_validation_matches_backend_name_rules(self):
        base={"album_summary":"Summary","description":"Description","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Garden Light","Gentle Summer Elegance","Serene Moments By Water","Together Near The Garden"]}
        self.assertEqual(base,validate_writer_payload(base))
        for names in (["Only One"],base["suggested_names"][:-1]+["lowercase name"],base["suggested_names"][:-1]+["Private Photo"],
                ["Bamboo Garden","Quiet Retreat","Summer Reverie","Golden Afternoon","Gentle Elegance","Serene Moments"]):
            with self.assertRaises(ProviderError):validate_writer_payload({**base,"suggested_names":names})

    def test_writer_validation_identifies_forbidden_title_and_word(self):
        payload={"album_summary":"Summary","description":"Description","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Garden Light","Gentle Summer Elegance","Serene Moments By Water","Romantic Pillow Talk Session"]}
        with self.assertRaises(ProviderError) as raised:validate_writer_payload(payload)
        self.assertIn('"Romantic Pillow Talk Session"',str(raised.exception))
        self.assertIn('forbidden word "Session"',str(raised.exception))

    def test_writer_retry_feedback_rejects_repeating_invalid_title(self):
        invalid={"album_summary":"Summary","description":"Description","suggested_names":
            ["Bamboo Garden","Quiet Retreat","Summer Garden Light","Gentle Summer Elegance","Serene Moments By Water","Romantic Pillow Talk Session"]}
        valid={**invalid,"suggested_names":invalid["suggested_names"][:-1]+["Romantic Pillow Talk Dreams"]}
        class Provider:
            def __init__(self):self.calls=[]
            def complete(self,prompt,**kwargs):
                self.calls.append(prompt);return (invalid if len(self.calls)==1 else valid),{}
        provider=Provider();result,_=AnalysisWorkflow(object(),provider,sleep=lambda _:None).writer({}, {})
        self.assertEqual(valid,result);self.assertIn("do not repeat the invalid title or forbidden word",provider.calls[1])

    def test_writer_replaces_roman_and_repeated_letter_four_word_fillers(self):
        from workers.ai_worker.workflow import normalize_writer_titles
        payload={"album_summary":"Summary","description":"Description","suggested_names":[
            "Whispering Lilies","Silken Temptation","Moonlit Lovers' Dance","Ethereal Elegance Reimagined",
            "Whispers Between Sheets II","Silken Shadows Unveiled IIIIIIIIIIIIIIIIIIIIIIII"]}
        normalized,count=normalize_writer_titles(payload)
        self.assertEqual(2,count)
        self.assertEqual("Whispers Between Sheets",normalized["suggested_names"][4])
        self.assertEqual("Silken Shadows Unveiled",normalized["suggested_names"][5])
        self.assertEqual("Whispers Between Sheets II",payload["suggested_names"][4])
        self.assertEqual(normalized,validate_writer_payload(normalized))

    def test_runtime_preserves_provider_failure_category(self):
        class Client:
            def __init__(self):self.failure=None
            def prepare_manifest(self,*_):raise ProviderError("safe failure",error_code="MODEL_PROVIDER_CONTEXT_FAILED")
            def heartbeat(self,*_):pass
            def fail_work(self,*args):self.failure=args
        client=Client();claimed={"uuid":"item-1","worker_kind":"album_name_analysis","configuration_snapshot":{}}
        with self.assertRaises(ProviderError):WorkerRuntime(client,object()).run_once(claimed)
        self.assertEqual("MODEL_PROVIDER_CONTEXT_FAILED",client.failure[1])
