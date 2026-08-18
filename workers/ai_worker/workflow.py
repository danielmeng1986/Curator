"""Two-stage Album-analysis orchestration and prompt ownership."""
from __future__ import annotations
import json
import hashlib
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
with an uppercase letter and contain only letters, apostrophes, or hyphens. Write sensual, provocative,
imaginative editorial titles that create intrigue and fantasy through atmosphere, tension, invitation, mood,
metaphor, or elegant wordplay. Avoid neutral descriptions, production labels, explicit anatomy, and literal
combinations of clothing, pose, room, media-category, or shooting terms. Avoid title words such as Adult,
Content, Shoot, Shoots, Posing, Displaying, Genital, Area, Interior, Photo, Photos, Collection, Session, or
Gallery. Do not describe explicit sexual acts or identify a person. Vision JSON:\n{vision}"""
FORBIDDEN_NAME_WORDS={"photo","photos","collection","session","gallery"}
NATURAL_TITLE_POLICY_VERSION="writer-natural-title-v1"
WRITER_REPAIR_TEMPERATURE=0.1

def _writer_attempt_settings(settings,attempt):
    """Derive observable sampling parameters from Work Item and repair attempts."""
    result=dict(settings or {})
    material=f"{result.get('_work_item_uuid','unbound')}:{result.get('_work_item_attempt',1)}:{attempt+1}"
    result["writer_seed"]=int.from_bytes(hashlib.sha256(material.encode()).digest()[:4],"big") & 0x7fffffff
    result["writer_generation_attempt"]=attempt+1
    result.setdefault("writer_temperature",0)
    if attempt:
        result["writer_temperature"]=max(float(result.get("writer_temperature",0)),WRITER_REPAIR_TEMPERATURE)
    return result

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
        if len(words) not in {2,3,4}:
            raise ProviderError(f'Suggested name "{name}" contains {len(words)} words; each name must contain 2-4 words.',
                error_code="MODEL_OUTPUT_INVALID")
        invalid_words=[word for word in words if not re.fullmatch(r"[A-Z][A-Za-z'’-]*",word)]
        if invalid_words:
            raise ProviderError(f'Suggested name "{name}" contains invalid word "{invalid_words[0]}"; every word must be capitalized English letters.',
                error_code="MODEL_OUTPUT_INVALID")
        forbidden_words=[word for word in words if word.casefold() in FORBIDDEN_NAME_WORDS]
        if forbidden_words:
            raise ProviderError(f'Suggested name "{name}" contains forbidden word "{forbidden_words[0]}".',
                error_code="MODEL_OUTPUT_INVALID")
        normalized.append(name);word_counts.append(len(words))
    if sorted(word_counts) not in ([2,2,3,3,3,3],[2,2,3,3,3,4],[2,2,3,3,4,4]):
        raise ProviderError("Writer names must contain two 2-word names, at least two 3-word names, and natural 3-or-4-word remaining names.",error_code="MODEL_OUTPUT_INVALID")
    return {"album_summary":_bounded_text(payload["album_summary"],"album_summary",500),
        "description":_bounded_text(payload["description"],"description",2000),"suggested_names":normalized}

def normalize_writer_titles(payload):
    """Remove obvious constrained-decoding filler while preserving natural titles."""
    if not isinstance(payload,dict) or not isinstance(payload.get("suggested_names"),list):return payload,0
    result=dict(payload);names=list(payload["suggested_names"]);replacements=0
    for index in (4,5):
        if index>=len(names) or not isinstance(names[index],str):continue
        words=names[index].split();tail=words[-1] if words else ""
        roman_filler=bool(re.fullmatch(r"[IVXLCDM]{2,}",tail))
        repeated_filler=bool(re.fullmatch(r"(.)\1{3,}",tail,re.IGNORECASE))
        if (roman_filler or repeated_filler) and len(words)==4:
            candidate=" ".join(words[:-1])
            if candidate in names[:index]+names[index+1:]:
                raise ProviderError(f'Suggested name "{names[index]}" contains filler, but removing it would duplicate "{candidate}". Replace the complete title with a distinct name.',error_code="MODEL_OUTPUT_INVALID")
            names[index]=candidate;replacements+=1
    result["suggested_names"]=names
    return result,replacements

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
            attempt_settings=_writer_attempt_settings(settings,attempt)
            try:payload,metrics=self.writer_provider.complete(prompt,settings=attempt_settings)
            except ProviderError:
                if attempt==self.retries:raise
                self.sleep(2**attempt);continue
            try:
                payload,replacements=normalize_writer_titles(payload)
                validated=validate_writer_payload(payload)
                if replacements:
                    metrics=dict(metrics or {});metrics["writer_natural_title_policy"]=NATURAL_TITLE_POLICY_VERSION
                    metrics["writer_filler_words_removed"]=replacements
                return validated,metrics
            except ProviderError as exc:
                if attempt==self.retries:raise
                previous_names=json.dumps(payload.get("suggested_names") if isinstance(payload,dict) else None,ensure_ascii=True)
                prompt=(f"{base}\nWriter repair attempt {attempt+2} of {self.retries+1}. "
                    f"Your previous suggested_names were: {previous_names}. Your previous response failed validation: {exc} "
                    "Replace every invalid or duplicated suggested name, regenerate the complete JSON object, and do not repeat the invalid title or forbidden word.")
                self.sleep(2**attempt)
