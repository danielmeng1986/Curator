"""Provider-neutral translation integration and secure local configuration."""
from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from urllib import error, request


class TranslationConfigurationError(Exception):
    pass


class TranslationProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def load_translation_config(repo_root: Path, environ=None) -> dict:
    """Load only Curator's DeepL settings; never interpret the file as shell."""
    env = os.environ if environ is None else environ
    values = {key: env.get(key) for key in ("CURATOR_DEEPL_API_KEY", "CURATOR_DEEPL_API_PLAN")}
    path = repo_root / ".env"
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise TranslationConfigurationError("The repository .env must be a regular file.")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise TranslationConfigurationError("The repository .env must have permission mode 0600.")
        parsed = {}
        for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
            if not match:
                raise TranslationConfigurationError(f"The repository .env has an invalid assignment on line {number}.")
            key, value = match.groups()
            if key not in values:
                continue
            if key in parsed:
                raise TranslationConfigurationError(f"The repository .env contains duplicate {key} assignments.")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            elif any(token in value for token in ("$(", "${", "`")):
                raise TranslationConfigurationError(f"The repository .env contains unsupported syntax on line {number}.")
            parsed[key] = value
        for key, value in parsed.items():
            if values[key] is None:
                values[key] = value
    plan = (values["CURATOR_DEEPL_API_PLAN"] or "developer").strip().lower()
    if plan not in {"developer", "growth"}:
        raise TranslationConfigurationError("CURATOR_DEEPL_API_PLAN must be developer or growth.")
    api_key = (values["CURATOR_DEEPL_API_KEY"] or "").strip()
    return {"api_key": api_key, "plan": plan, "configured": bool(api_key)}


class DeepLTranslationAdapter:
    PROVIDER = "deepl"
    MODEL = "text-v2"
    ENDPOINTS = {
        "developer": "https://api-free.deepl.com/v2/translate",
        "growth": "https://api.deepl.com/v2/translate",
    }

    def __init__(self, api_key: str, plan: str = "developer", timeout: float = 10, opener=None):
        self._api_key, self._plan, self._timeout = api_key, plan, timeout
        self._opener = opener or request.urlopen

    def translate(self, texts: list[str], target_lang: str = "ZH-HANS") -> list[dict]:
        if not texts or len(texts) > 50 or sum(len(item) for item in texts) > 10000:
            raise TranslationProviderError("TRANSLATION_REQUEST_INVALID", "Translation request is outside the supported bounds.")
        payload = json.dumps({"text": texts, "source_lang": "EN", "target_lang": target_lang}).encode()
        req = request.Request(self.ENDPOINTS[self._plan], data=payload, method="POST", headers={
            "Authorization": f"DeepL-Auth-Key {self._api_key}", "Content-Type": "application/json",
        })
        try:
            with self._opener(req, timeout=self._timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise TranslationProviderError("TRANSLATION_PROVIDER_INVALID_RESPONSE", "Translation provider response was too large.")
            decoded = json.loads(raw)
            rows = decoded.get("translations") if isinstance(decoded, dict) else None
            if not isinstance(rows, list) or len(rows) != len(texts):
                raise ValueError
            result = []
            for row in rows:
                translated = row.get("text") if isinstance(row, dict) else None
                if not isinstance(translated, str) or not translated.strip():
                    raise ValueError
                result.append({"text": translated.strip(), "detected_source_language": row.get("detected_source_language")})
            return result
        except error.HTTPError as exc:
            code = "TRANSLATION_PROVIDER_AUTH" if exc.code in {401, 403} else \
                "TRANSLATION_PROVIDER_QUOTA" if exc.code == 456 else "TRANSLATION_PROVIDER_UNAVAILABLE"
            raise TranslationProviderError(code, "Translation provider rejected the request.") from None
        except TranslationProviderError:
            raise
        except (error.URLError, TimeoutError):
            raise TranslationProviderError("TRANSLATION_PROVIDER_UNAVAILABLE", "Translation provider is unavailable.") from None
        except (ValueError, json.JSONDecodeError):
            raise TranslationProviderError("TRANSLATION_PROVIDER_INVALID_RESPONSE", "Translation provider returned an invalid response.") from None
