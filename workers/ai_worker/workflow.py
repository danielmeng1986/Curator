"""Two-stage Album-analysis orchestration and prompt ownership."""
from __future__ import annotations
import json
import re
import time
from .provider import ProviderError
from apps.ai_instruction_profile import compose

VISION_PROMPT="""Analyze all supplied Album evidence images together. Return exactly one JSON object and no other
fields, using this shape: {"scene":"...","people":{"minimum":0,"maximum":0},
"location_environment":"...","subjects":[],"objects":[],"actions":[],"confidence":0.0,"warnings":[]}.
minimum and maximum must be integers from 0 to 100, confidence must be a number from 0 to 1, and the four list
fields must contain strings. Do not identify people."""
WRITER_PROMPT="""Using the following Vision JSON, return one JSON object only with album_summary (string),
description (string), and suggested_names (exactly six unique names): exactly two names of two English words,
exactly two names of three English words, and exactly two names of four English words. Every word must start
with an uppercase letter and contain only letters, apostrophes, or hyphens.
Never use Photo, Photos, Collection, Session, or Gallery as a word. Vision JSON:\n{vision}"""
FORBIDDEN_NAME_WORDS={"photo","photos","collection","session","gallery"}

def _bounded_array(payload,key,maximum,text_limit):
    values=payload[key]
    if not isinstance(values,list) or len(values)>maximum:
        raise ProviderError(f"Vision {key} must be a bounded array.",error_code="MODEL_OUTPUT_INVALID")
    return [_bounded_text(value,key,text_limit) for value in values]

def validate_vision_payload(payload):
    required={"scene","people","location_environment","subjects","objects","actions","confidence","warnings"}
    if not isinstance(payload,dict) or set(payload)!=required:
        raise ProviderError("Vision fields must exactly match schema v1.",error_code="MODEL_OUTPUT_INVALID")
    people=payload["people"]
    if not isinstance(people,dict) or set(people)!={"minimum","maximum"} \
            or any(isinstance(people[key],bool) or not isinstance(people[key],int) or not 0<=people[key]<=100 for key in people) \
            or people["minimum"]>people["maximum"]:
        raise ProviderError("Vision people must contain a valid integer minimum/maximum range.",error_code="MODEL_OUTPUT_INVALID")
    confidence=payload["confidence"]
    if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not 0<=confidence<=1:
        raise ProviderError("Vision confidence must be a number from 0 to 1.",error_code="MODEL_OUTPUT_INVALID")
    return {"scene":_bounded_text(payload["scene"],"scene",500),"people":people,
        "location_environment":_bounded_text(payload["location_environment"],"location_environment",500),
        "subjects":_bounded_array(payload,"subjects",50,120),"objects":_bounded_array(payload,"objects",50,120),
        "actions":_bounded_array(payload,"actions",50,120),"confidence":confidence,
        "warnings":_bounded_array(payload,"warnings",20,300)}

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
    normalized=[];word_counts=[]
    for value in names:
        name=_bounded_text(value,"suggested name",120);words=name.split()
        if len(words) not in {2,3,4} or any(not re.fullmatch(r"[A-Z][A-Za-z'’-]*",word) for word in words) \
                or any(word.casefold() in FORBIDDEN_NAME_WORDS for word in words):
            raise ProviderError("Each suggested name must contain 2-4 capitalized English words and no forbidden term.",error_code="MODEL_OUTPUT_INVALID")
        normalized.append(name);word_counts.append(len(words))
    if sorted(word_counts)!=[2,2,3,3,4,4]:
        raise ProviderError("Writer suggested_names must contain exactly two 2-word, two 3-word, and two 4-word names.",error_code="MODEL_OUTPUT_INVALID")
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
    def vision(self,images,settings):
        profile=settings.get("instruction_profile")
        prompt=compose(profile,"vision") if profile else VISION_PROMPT
        base=prompt
        for attempt in range(self.retries+1):
            try:payload,metrics=self.provider.complete(prompt,images=images,settings=settings)
            except ProviderError:
                if attempt==self.retries:raise
                self.sleep(2**attempt);continue
            try:return validate_vision_payload(payload),metrics
            except ProviderError as exc:
                if attempt==self.retries:raise
                prompt=f"{base}\nYour previous response failed validation: {exc} Regenerate the complete JSON object and obey every rule."
                self.sleep(2**attempt)
    def writer(self,vision,settings):
        profile=settings.get("instruction_profile")
        base=compose(profile,"writer",vision=vision) if profile else WRITER_PROMPT.format(vision=json.dumps(vision,sort_keys=True))
        prompt=base
        for attempt in range(self.retries+1):
            try:payload,metrics=self.writer_provider.complete(prompt,settings=settings)
            except ProviderError:
                if attempt==self.retries:raise
                self.sleep(2**attempt);continue
            try:return validate_writer_payload(payload),metrics
            except ProviderError as exc:
                if attempt==self.retries:raise
                prompt=f"{base}\nYour previous response failed validation: {exc} Regenerate the complete JSON object and obey every rule."
                self.sleep(2**attempt)
