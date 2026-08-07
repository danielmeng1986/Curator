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
    def health(self) -> dict: return self.get("/health")
