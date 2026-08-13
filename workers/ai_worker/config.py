"""Private Worker state and configuration."""
from __future__ import annotations
import json
import os
import secrets
import uuid
from pathlib import Path

DEFAULT_STATE=Path.home()/".config"/"curator"/"ai-worker.json"

def load(path=DEFAULT_STATE):
    path=Path(path)
    if not path.is_file(): raise ValueError(f"Worker state not found: {path}")
    if os.name!="nt" and path.stat().st_mode & 0o077: raise ValueError("Worker state permissions must be 0600.")
    value=json.loads(path.read_text())
    if not isinstance(value,dict): raise ValueError("Worker state is invalid.")
    return value

def save(value,path=DEFAULT_STATE):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.parent.chmod(0o700)
    temporary=path.with_suffix(".tmp");temporary.write_text(json.dumps(value,indent=2)+"\n");temporary.chmod(0o600);temporary.replace(path);path.chmod(0o600)

def enrollment_material(base_url,device_name):
    return {"version":1,"backend_url":base_url.rstrip("/"),"device_name":device_name,
        "device_identity":str(uuid.uuid4()),"token":secrets.token_urlsafe(32),
        "enrollment_proof":secrets.token_urlsafe(32),"status":"New"}
