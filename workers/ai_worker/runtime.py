"""Runnable Worker lifecycle with no Backend or SQLite dependency."""
from __future__ import annotations
import hashlib
import tempfile
import threading
from pathlib import Path

def payload_data(response): return response.get("data",response)

class LeaseHeartbeat:
    def __init__(self,client,item_uuid,lease_seconds,interval=None):
        self.client,self.item_uuid,self.lease_seconds=client,item_uuid,lease_seconds
        self.interval=interval or max(20,lease_seconds//3);self.stop_event=threading.Event();self.error=None;self.thread=None
    def __enter__(self):
        def run():
            while not self.stop_event.wait(self.interval):
                try:self.client.heartbeat(self.item_uuid,self.lease_seconds)
                except Exception as exc:self.error=exc;self.stop_event.set()
        self.thread=threading.Thread(target=run,name="curator-worker-heartbeat",daemon=True);self.thread.start();return self
    def ensure(self):
        if self.error: raise RuntimeError("Work Item heartbeat failed.") from self.error
    def __exit__(self,*_):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=5)

class WorkerRuntime:
    def __init__(self,client,workflow,*,worker_kind="album_name_analysis",lease_seconds=300,temp_root=None):
        self.client,self.workflow,self.worker_kind,self.lease_seconds=client,workflow,worker_kind,lease_seconds;self.temp_root=temp_root
    def run_once(self,claimed=None):
        claimed=claimed or payload_data(self.client.claim_work(self.worker_kind,self.lease_seconds,0)).get("item")
        if not claimed:return None
        item_uuid=claimed["uuid"]
        try:
            if claimed.get("worker_kind")!=self.worker_kind:
                self.client.fail_work(item_uuid,"WORKER_KIND_MISMATCH","Claimed Work Item kind does not match this Worker process.")
                raise RuntimeError("Claimed Work Item kind does not match this Worker process.")
            with LeaseHeartbeat(self.client,item_uuid,self.lease_seconds) as heartbeat:
                manifest=payload_data(self.client.prepare_manifest(item_uuid))["manifest"]
                settings=dict(claimed["configuration_snapshot"])
                settings["_work_item_uuid"]=item_uuid;settings["_work_item_attempt"]=claimed.get("attempt_count",1)
                result_state=claimed.get("result_state","AwaitingVision")
                if result_state=="AwaitingWriter":
                    vision=claimed.get("accepted_vision")
                    if not isinstance(vision,dict):raise RuntimeError("AwaitingWriter claim is missing its accepted Vision result.")
                elif result_state=="AwaitingVision":
                    with tempfile.TemporaryDirectory(prefix="curator-ai-worker-",dir=self.temp_root) as directory:
                        paths=[]
                        for evidence in manifest["evidence"]:
                            content=self.client.download_evidence(evidence["uuid"])
                            if len(content)!=evidence["size_bytes"] or hashlib.sha256(content).hexdigest()!=evidence["sha256"]:
                                raise RuntimeError("Downloaded evidence failed integrity validation.")
                            suffix={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[evidence["mime_type"]]
                            path=Path(directory)/f"evidence-{evidence['ordinal']}{suffix}";path.write_bytes(content);path.chmod(0o600);paths.append(path)
                        vision,vision_metrics=self.workflow.vision(paths,settings);heartbeat.ensure()
                        self.client.submit_vision(item_uuid,vision,vision_metrics)
                else:raise RuntimeError(f"Claimed Work Item has unsupported result state: {result_state}.")
                writer,writer_metrics=self.workflow.writer(vision,settings);heartbeat.ensure()
                self.client.submit_writer(item_uuid,writer,writer_metrics)
            return item_uuid
        except KeyboardInterrupt: raise
        except Exception as exc:
            error_code=getattr(exc,"error_code","WORKER_EXECUTION_FAILED")
            try:self.client.fail_work(item_uuid,error_code,str(exc)[:1000] or "Worker execution failed")
            except Exception:pass
            raise
