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
    def __init__(self,client,workflow,*,lease_seconds=300,temp_root=None):
        self.client,self.workflow,self.lease_seconds=client,workflow,lease_seconds;self.temp_root=temp_root
    def run_once(self,claimed=None):
        claimed=claimed or payload_data(self.client.claim_work(self.lease_seconds)).get("item")
        if not claimed:return None
        item_uuid=claimed["uuid"]
        try:
            with LeaseHeartbeat(self.client,item_uuid,self.lease_seconds) as heartbeat:
                manifest=payload_data(self.client.prepare_manifest(item_uuid))["manifest"]
                with tempfile.TemporaryDirectory(prefix="curator-ai-worker-",dir=self.temp_root) as directory:
                    paths=[]
                    for evidence in manifest["evidence"]:
                        content=self.client.download_evidence(evidence["uuid"])
                        if len(content)!=evidence["size_bytes"] or hashlib.sha256(content).hexdigest()!=evidence["sha256"]:
                            raise RuntimeError("Downloaded evidence failed integrity validation.")
                        suffix={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[evidence["mime_type"]]
                        path=Path(directory)/f"evidence-{evidence['ordinal']}{suffix}";path.write_bytes(content);path.chmod(0o600);paths.append(path)
                    settings=claimed["configuration_snapshot"]
                    vision,vision_metrics=self.workflow.vision(paths,settings);heartbeat.ensure()
                    self.client.submit_vision(item_uuid,vision,vision_metrics)
                    writer,writer_metrics=self.workflow.writer(vision,settings);heartbeat.ensure()
                    self.client.submit_writer(item_uuid,writer,writer_metrics)
            return item_uuid
        except KeyboardInterrupt: raise
        except Exception as exc:
            try:self.client.fail_work(item_uuid,"WORKER_EXECUTION_FAILED",str(exc)[:1000] or "Worker execution failed")
            except Exception:pass
            raise
