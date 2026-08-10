"""Authenticated Curator API client; deliberately has no SQLite dependency."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class CuratorApiError(RuntimeError): pass

class CuratorClient:
    def __init__(self, base_url: str, token: str, opener=urlopen):
        self.base_url, self.token, self._opener = base_url.rstrip("/"), token, opener
    def get(self, path: str) -> dict:
        request = Request(f"{self.base_url}/api/v1{path}", headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        try:
            with self._opener(request, timeout=10) as response: return json.loads(response.read())
        except HTTPError as exc: raise CuratorApiError(f"Backend rejected request: HTTP {exc.code}") from exc
        except URLError as exc: raise CuratorApiError("Backend unavailable; retry the worker request.") from exc
    def post(self, path: str, body: dict) -> dict:
        request = Request(f"{self.base_url}/api/v1{path}", data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json", "Content-Type": "application/json"})
        try:
            with self._opener(request, timeout=10) as response: return json.loads(response.read())
        except HTTPError as exc: raise CuratorApiError(f"Backend rejected request: HTTP {exc.code}") from exc
        except URLError as exc: raise CuratorApiError("Backend unavailable; retry the worker request.") from exc
    def claim_work(self, lease_seconds: int = 300) -> dict: return self.post("/ai-work-items/claim", {"lease_seconds": lease_seconds})
    def heartbeat(self, item_uuid: str, lease_seconds: int = 300) -> dict:
        return self.post(f"/ai-work-items/{item_uuid}/heartbeat", {"lease_seconds": lease_seconds})
    def fail_work(self, item_uuid: str, error_code: str, message: str) -> dict:
        return self.post(f"/ai-work-items/{item_uuid}/fail", {"error_code": error_code, "message": message})
    def submit_vision(self, item_uuid: str, payload: dict, runtime_metrics: dict | None = None) -> dict:
        return self.post(f"/ai-work-items/{item_uuid}/results/vision", {
            "schema_version": "curator://album-analysis/vision/v1", "payload": payload,
            "runtime_metrics": runtime_metrics or {}})
    def submit_writer(self, item_uuid: str, payload: dict, runtime_metrics: dict | None = None) -> dict:
        return self.post(f"/ai-work-items/{item_uuid}/results/writer", {
            "schema_version": "curator://album-analysis/writer/v1", "payload": payload,
            "runtime_metrics": runtime_metrics or {}})
    def evidence_metadata(self, evidence_uuid: str) -> dict: return self.get(f"/ai-evidence/{evidence_uuid}")
    def download_evidence(self, evidence_uuid: str) -> bytes:
        request = Request(f"{self.base_url}/api/v1/ai-evidence/{evidence_uuid}/content",
            headers={"Authorization":f"Bearer {self.token}","Accept":"image/jpeg,image/png,image/webp"})
        try:
            with self._opener(request,timeout=30) as response: return response.read()
        except HTTPError as exc: raise CuratorApiError(f"Backend rejected evidence: HTTP {exc.code}") from exc
        except URLError as exc: raise CuratorApiError("Backend unavailable during evidence transfer.") from exc
    def health(self) -> dict: return self.get("/health")
