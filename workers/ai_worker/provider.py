"""llama.cpp command provider with bounded JSON extraction."""
from __future__ import annotations
import json
import subprocess
import time

class ProviderError(RuntimeError): pass

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
        settings=settings or {}; args=[self.cli,"-m",self.model,"-p",prompt,"--no-display-prompt",
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
        except (OSError,subprocess.SubprocessError) as exc:
            raise ProviderError("Model provider failed; no Curator result was submitted.") from exc
        return parse_json_object(result.stdout),{"duration_ms":round((time.monotonic()-started)*1000),"provider":"llama_cpp"}
