"""Suggestion-only workflow. Results remain local until an AI Workspace exists."""
from __future__ import annotations
import time
from .provider import ProviderError
class AnalysisWorkflow:
    def __init__(self, provider, retries: int = 2, sleep=time.sleep): self.provider, self.retries, self.sleep = provider, retries, sleep
    def analyze(self, prompt: str) -> dict:
        for attempt in range(self.retries + 1):
            try: return {"status": "suggestion_only", "output": self.provider.complete(prompt), "attempt": attempt + 1}
            except ProviderError:
                if attempt == self.retries: raise
                self.sleep(2 ** attempt)
