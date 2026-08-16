"""llama.cpp command provider with bounded JSON extraction."""
from __future__ import annotations
import json
import re
import subprocess
import time

class ProviderError(RuntimeError):
    def __init__(self,message: str,*,error_code: str="MODEL_PROVIDER_FAILED"):
        super().__init__(message);self.error_code=error_code

REQUIRED_MTMD_OPTIONS=("--mmproj","--image","--image-max-tokens","--gpu-layers")
REQUIRED_TEXT_OPTIONS=("--single-turn","--simple-io","--no-display-prompt","--no-show-timings","--json-schema","--gpu-layers")
DIAGNOSTIC_LIMIT=700

def _validate_cli(cli: str,required_options,display_name: str) -> None:
    try:
        result=subprocess.run([cli,"--help"],capture_output=True,text=True,timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise ProviderError(f"{display_name} compatibility check timed out.",error_code="MODEL_PROVIDER_TIMEOUT") from exc
    except OSError as exc:
        raise ProviderError(f"{display_name} compatibility check could not start.",error_code="MODEL_PROVIDER_EXECUTABLE_INVALID") from exc
    help_text=f"{result.stdout}\n{result.stderr}"
    missing=[option for option in required_options if option not in help_text]
    if missing:
        raise ProviderError(f"{display_name} is missing required options: {', '.join(missing)}.",
            error_code="MODEL_PROVIDER_ARGUMENT_INVALID")

def validate_mtmd_cli(cli: str) -> None:
    """Reject an incompatible multimodal executable before claiming evidence."""
    _validate_cli(cli,REQUIRED_MTMD_OPTIONS,"llama-mtmd-cli")

def validate_text_cli(cli: str) -> None:
    """Reject an interactive-only text executable before claiming work."""
    _validate_cli(cli,REQUIRED_TEXT_OPTIONS,"llama-cli")

def _safe_diagnostic(value: str|None,redactions) -> str:
    text=str(value or "")
    for secret in redactions:
        if secret:text=text.replace(str(secret),"[redacted]")
    text=re.sub(r"(?i)\b(authorization|bearer|token|password|secret|api[_-]?key)\s*[:=]\s*\S+",r"\1=[redacted]",text)
    text=re.sub(r"curator-ai-worker-[^/\\\s]+","curator-ai-worker-[redacted]",text)
    text=" ".join(text.split())
    return text[:DIAGNOSTIC_LIMIT]

def _failure_code(diagnostic: str) -> str:
    lowered=diagnostic.casefold()
    if any(value in lowered for value in ("unknown argument","unknown option","unrecognized option","invalid argument")):
        return "MODEL_PROVIDER_ARGUMENT_INVALID"
    if any(value in lowered for value in ("mmproj","projector","vision model")):
        return "MODEL_PROVIDER_PROJECTOR_FAILED"
    if any(value in lowered for value in ("out of memory","cuda","vulkan","sycl","metal")):
        return "MODEL_PROVIDER_ACCELERATOR_FAILED"
    if any(value in lowered for value in ("context size","context length","kv cache","n_ctx")):
        return "MODEL_PROVIDER_CONTEXT_FAILED"
    if any(value in lowered for value in ("failed to load model","error loading model","model load")):
        return "MODEL_PROVIDER_MODEL_LOAD_FAILED"
    return "MODEL_PROVIDER_FAILED"

def parse_json_object(output: str) -> dict:
    decoder=json.JSONDecoder()
    for index,char in enumerate(output):
        if char != "{": continue
        try:
            value,_=decoder.raw_decode(output[index:])
            if isinstance(value,dict): return value
        except json.JSONDecodeError: continue
    raise ProviderError("Model output did not contain a JSON object.")

class LlamaCliProvider:
    def __init__(self, cli: str, model: str, *, mmproj: str|None=None, timeout_seconds: int=900):
        self.cli,self.model,self.mmproj,self.timeout_seconds=cli,model,mmproj,timeout_seconds
    def complete(self, prompt: str, *, images=(), settings=None) -> tuple[dict,dict]:
        settings=settings or {}; args=[self.cli,"-m",self.model,"-p",prompt,
            "-c",str(settings.get("context_size",4096)),"-t",str(settings.get("threads",1)),
            "-ngl",str(settings.get("gpu_layers",0)),"-n",str(settings.get("max_tokens",512)),
            "--temp",str(settings.get("temperature",0))]
        if self.mmproj: args += ["--mmproj",self.mmproj]
        if images:
            args += ["--image",",".join(str(path) for path in images),
                "--image-max-tokens",str(settings.get("image_max_tokens",384))]
        started=time.monotonic()
        try:
            result=subprocess.run(args,check=True,capture_output=True,text=True,timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("Model provider timed out; no Curator result was submitted.",error_code="MODEL_PROVIDER_TIMEOUT") from exc
        except subprocess.CalledProcessError as exc:
            diagnostic=_safe_diagnostic(exc.stderr or exc.stdout,[prompt,self.model,self.mmproj,*images])
            message="Model provider failed"
            if diagnostic:message+=f": {diagnostic}"
            raise ProviderError(f"{message}; no Curator result was submitted.",error_code=_failure_code(diagnostic)) from exc
        except OSError as exc:
            raise ProviderError("Model provider could not start; no Curator result was submitted.",
                error_code="MODEL_PROVIDER_EXECUTABLE_INVALID") from exc
        return parse_json_object(result.stdout),{"duration_ms":round((time.monotonic()-started)*1000),"provider":"llama_cpp"}

class LlamaTextCliProvider(LlamaCliProvider):
    """Non-interactive, single-turn Writer provider using standard llama-cli."""
    def __init__(self,cli: str,model: str,*,timeout_seconds: int=900):
        super().__init__(cli,model,timeout_seconds=timeout_seconds)
    def complete(self,prompt: str,*,images=(),settings=None,json_schema=None) -> tuple[dict,dict]:
        if images:raise ProviderError("Text model provider does not accept images.",error_code="MODEL_PROVIDER_ARGUMENT_INVALID")
        settings=settings or {};args=[self.cli,"-m",self.model,"-p",prompt,
            "-c",str(settings.get("context_size",4096)),"-t",str(settings.get("threads",1)),
            "-ngl",str(settings.get("gpu_layers",0)),"-n",str(settings.get("max_tokens",512)),
            "--temp",str(settings.get("temperature",0)),"--single-turn","--simple-io",
            "--no-display-prompt","--no-show-timings"]
        if json_schema:args += ["--json-schema",json.dumps(json_schema,separators=(",",":"),ensure_ascii=True)]
        started=time.monotonic()
        try:
            result=subprocess.run(args,check=True,capture_output=True,text=True,timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            raise ProviderError("Text model provider timed out; no Curator result was submitted.",error_code="MODEL_PROVIDER_TIMEOUT") from exc
        except subprocess.CalledProcessError as exc:
            diagnostic=_safe_diagnostic(exc.stderr or exc.stdout,[prompt,self.model])
            message="Text model provider failed"
            if diagnostic:message+=f": {diagnostic}"
            raise ProviderError(f"{message}; no Curator result was submitted.",error_code=_failure_code(diagnostic)) from exc
        except OSError as exc:
            raise ProviderError("Text model provider could not start; no Curator result was submitted.",
                error_code="MODEL_PROVIDER_EXECUTABLE_INVALID") from exc
        return parse_json_object(result.stdout),{"duration_ms":round((time.monotonic()-started)*1000),"provider":"llama_cpp"}
