"""Two-stage Album-analysis orchestration and prompt ownership."""
from __future__ import annotations
import json
import re
import time
from .provider import ProviderError

VISION_PROMPT="""Analyze all supplied Album evidence images together. Return JSON only with exactly these fields:
scene (string), people ({minimum, maximum} integers), location_environment (string), subjects (string array),
objects (string array), actions (string array), confidence (0..1), warnings (string array). Do not identify people."""
WRITER_PROMPT="""Using the following Vision JSON, return one JSON object only with album_summary (string),
description (string), and suggested_names (exactly six unique names). Every suggested name must contain 2-5
English words; every word must start with an uppercase letter and contain only letters, apostrophes, or hyphens.
Never use Photo, Photos, Collection, Session, or Gallery as a word. Vision JSON:\n{vision}"""
WRITER_JSON_SCHEMA={"type":"object","additionalProperties":False,
    "required":["album_summary","description","suggested_names"],"properties":{
        # Keep the generation grammar deliberately structural. llama.cpp expands
        # large JSON-Schema string bounds into repeated grammar rules and rejects
        # otherwise valid schemas once that expansion exceeds its sane defaults.
        # Curator's exact string bounds remain enforced by validate_writer_payload
        # below and by the Backend before persistence.
        "album_summary":{"type":"string"},
        "description":{"type":"string"},
        "suggested_names":{"type":"array","minItems":6,"maxItems":6,"uniqueItems":True,
            "items":{"type":"string"}}}}
FORBIDDEN_NAME_WORDS={"photo","photos","collection","session","gallery"}

def _bounded_text(value,name,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(char)<32 and char not in "\n\t" for char in value):
        raise ProviderError(f"Writer {name} must be a non-empty bounded string.",error_code="MODEL_OUTPUT_INVALID")
    return value.strip()

def validate_writer_payload(payload):
    if not isinstance(payload,dict) or set(payload)!={"album_summary","description","suggested_names"}:
        raise ProviderError("Writer fields must be album_summary, description, and suggested_names only.",error_code="MODEL_OUTPUT_INVALID")
    names=payload["suggested_names"]
    if not isinstance(names,list) or len(names)!=6 or any(not isinstance(name,str) for name in names) or len(set(names))!=6:
        raise ProviderError("Writer suggested_names must contain exactly six unique strings.",error_code="MODEL_OUTPUT_INVALID")
    normalized=[]
    for value in names:
        name=_bounded_text(value,"suggested name",120);words=name.split()
        if not 2<=len(words)<=5 or any(not re.fullmatch(r"[A-Z][A-Za-z'’-]*",word) for word in words) \
                or any(word.casefold() in FORBIDDEN_NAME_WORDS for word in words):
            raise ProviderError("Each suggested name must contain 2-5 capitalized English words and no forbidden term.",error_code="MODEL_OUTPUT_INVALID")
        normalized.append(name)
    return {"album_summary":_bounded_text(payload["album_summary"],"album_summary",500),
        "description":_bounded_text(payload["description"],"description",2000),"suggested_names":normalized}

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
        base=WRITER_PROMPT.format(vision=json.dumps(vision,sort_keys=True))
        prompt=base
        for attempt in range(self.retries+1):
            try:payload,metrics=self.writer_provider.complete(prompt,settings=settings,json_schema=WRITER_JSON_SCHEMA)
            except ProviderError:
                if attempt==self.retries:raise
                self.sleep(2**attempt);continue
            try:return validate_writer_payload(payload),metrics
            except ProviderError as exc:
                if attempt==self.retries:raise
                prompt=f"{base}\nYour previous response failed validation: {exc} Regenerate the complete JSON object and obey every rule."
                self.sleep(2**attempt)
