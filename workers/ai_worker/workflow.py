"""Two-stage Album-analysis orchestration and prompt ownership."""
from __future__ import annotations
import time
from .provider import ProviderError

VISION_PROMPT="""Analyze all supplied Album evidence images together. Return JSON only with exactly these fields:
scene (string), people ({minimum, maximum} integers), location_environment (string), subjects (string array),
objects (string array), actions (string array), confidence (0..1), warnings (string array). Do not identify people."""
WRITER_PROMPT="""Using the following Vision JSON, return JSON only with album_summary (string), description (string),
and suggested_names (exactly six unique concise English names). Vision JSON:\n{vision}"""

class AnalysisWorkflow:
    def __init__(self, provider, writer_provider=None, retries:int=2, sleep=time.sleep):
        self.provider,self.writer_provider=provider,writer_provider or provider;self.retries,self.sleep=retries,sleep
    def _complete(self,provider,*args,**kwargs):
        for attempt in range(self.retries+1):
            try: return provider.complete(*args,**kwargs)
            except ProviderError:
                if attempt==self.retries: raise
                self.sleep(2**attempt)
    def analyze(self,prompt:str):
        for attempt in range(self.retries+1):
            try: return {"status":"suggestion_only","output":self.provider.complete(prompt),"attempt":attempt+1}
            except ProviderError:
                if attempt==self.retries: raise
                self.sleep(2**attempt)
    def vision(self,images,settings): return self._complete(self.provider,VISION_PROMPT,images=images,settings=settings)
    def writer(self,vision,settings):
        import json
        return self._complete(self.writer_provider,WRITER_PROMPT.format(vision=json.dumps(vision,sort_keys=True)),settings=settings)
