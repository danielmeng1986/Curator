"""Provider adapter boundary for llama.cpp-compatible command-line models."""
from __future__ import annotations
import subprocess
class ProviderError(RuntimeError): pass
class LlamaCliProvider:
    def __init__(self, cli: str, model: str): self.cli, self.model = cli, model
    def complete(self, prompt: str) -> str:
        try:
            result = subprocess.run([self.cli, "-m", self.model, "-p", prompt], check=True, capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.SubprocessError) as exc: raise ProviderError("Model provider failed; no Curator data was changed.") from exc
        return result.stdout.strip()
