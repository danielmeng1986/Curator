#!/usr/bin/env python3
"""Check Curator application-manual coverage, localization, links, and safety."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL_ROOT = ROOT / "Docs" / "User-Manual"
LOCALES = ("en", "zh-CN")
EXPECTED = {
    "server/apps-backend.md": ROOT / "apps" / "backend" / "__main__.py",
    "client/apps-web/README.md": ROOT / "apps" / "web" / "static" / "index.html",
    "client/apps-web/access-and-registration.md": ROOT / "apps" / "web" / "static" / "index.html",
    "client/apps-web/reader.md": ROOT / "apps" / "web" / "static" / "index.html",
    "client/apps-web/writer.md": ROOT / "apps" / "web" / "static" / "index.html",
    "client/apps-web/administrator.md": ROOT / "apps" / "web" / "static" / "index.html",
    "worker/ai-worker.md": ROOT / "workers" / "ai_worker" / "README.md",
}
REQUIRED_SECTIONS = {
    "server/apps-backend.md": {
        "purpose", "prerequisites", "configuration", "initialize", "lifecycle",
        "bootstrap", "security", "recovery", "upgrade", "troubleshooting",
        "warnings", "checklist",
    },
    "client/apps-web/README.md": {
        "purpose", "connect", "navigation", "roles", "feedback", "safety", "checklist",
    },
    "client/apps-web/access-and-registration.md": {
        "concepts", "bootstrap", "proof", "request", "approval", "connection",
        "lifecycle", "troubleshooting", "checklist",
    },
    "client/apps-web/reader.md": {
        "purpose", "login", "workflows", "denials", "security", "troubleshooting",
    },
    "client/apps-web/writer.md": {
        "purpose", "entities", "import", "issues", "operations", "denials", "checklist",
    },
    "client/apps-web/administrator.md": {
        "purpose", "bootstrap", "authentication", "issue-admin", "backup",
        "ai-config", "ai-review", "risk", "checklist",
    },
    "worker/ai-worker.md": {
        "purpose", "prerequisites", "source", "network", "access",
        "configuration", "workflow", "lifecycle", "troubleshooting",
        "security", "checklist",
    },
}
SECTION_RE = re.compile(r"<!--\s*manual-section:\s*([a-z0-9-]+)\s*-->")
LINK_RE = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```(?:bash|sh)\n(.*?)```", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(\d+)\.", re.MULTILINE)
SENSITIVE_RE = re.compile(
    r"(?:Authorization:\s*Bearer\s+\S+|curator\.web\.deviceToken\s*[=:]\s*['\"]?\S+)",
    re.IGNORECASE,
)


def manual_files(root: Path = MANUAL_ROOT) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for locale in LOCALES:
        locale_root = root / locale
        result[locale] = {
            path.relative_to(locale_root).as_posix()
            for path in locale_root.rglob("*.md")
        } if locale_root.exists() else set()
    return result


def inspect_pair(relative: str, root: Path = MANUAL_ROOT) -> list[str]:
    failures: list[str] = []
    texts: dict[str, str] = {}
    for locale in LOCALES:
        path = root / locale / relative
        if not path.is_file():
            failures.append(f"missing {locale} manual: {relative}")
            continue
        texts[locale] = path.read_text(encoding="utf-8")
    if len(texts) != len(LOCALES):
        return failures

    markers = {locale: SECTION_RE.findall(text) for locale, text in texts.items()}
    for locale, found in markers.items():
        missing = REQUIRED_SECTIONS[relative] - set(found)
        failures.extend(f"missing safety/structure section in {locale}/{relative}: {item}" for item in sorted(missing))
        if len(found) != len(set(found)):
            failures.append(f"duplicate section marker in {locale}/{relative}")
    if markers["en"] != markers["zh-CN"]:
        failures.append(f"section order differs between locales: {relative}")
    if HEADING_RE.findall(texts["en"]) != HEADING_RE.findall(texts["zh-CN"]):
        failures.append(f"numbered heading structure differs between locales: {relative}")
    if FENCE_RE.findall(texts["en"]) != FENCE_RE.findall(texts["zh-CN"]):
        failures.append(f"shell commands differ between locales: {relative}")
    if LINK_RE.findall(texts["en"]) != LINK_RE.findall(texts["zh-CN"]):
        failures.append(f"link targets differ between locales: {relative}")

    for locale, text in texts.items():
        path = root / locale / relative
        if SENSITIVE_RE.search(text):
            failures.append(f"possible embedded credential: {locale}/{relative}")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            clean_target = target.split("#", 1)[0]
            if clean_target and not (path.parent / clean_target).resolve().is_file():
                failures.append(f"broken link in {locale}/{relative}: {target}")
    return failures


def check(root: Path = MANUAL_ROOT) -> list[str]:
    failures: list[str] = []
    inventories = manual_files(root)
    expected = set(EXPECTED)
    for relative, entrypoint in EXPECTED.items():
        if not entrypoint.is_file():
            failures.append(f"supported application entry point missing: {entrypoint.relative_to(ROOT)}")
        failures.extend(inspect_pair(relative, root))
    for locale in LOCALES:
        missing = expected - inventories[locale]
        extra = inventories[locale] - expected
        failures.extend(f"missing required {locale} path: {item}" for item in sorted(missing))
        failures.extend(f"unpaired/unregistered {locale} path: {item}" for item in sorted(extra))
    if inventories["en"] != inventories["zh-CN"]:
        failures.append("English and Chinese manual file inventories differ")
    return failures


def main() -> int:
    failures = check()
    if failures:
        print("User manual release gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"User manual release gate: OK ({len(EXPECTED)} mirrored manuals, {len(LOCALES)} locales)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
