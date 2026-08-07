#!/usr/bin/env python3
"""Temporary compatibility launcher for the relocated Curator Backend.

The authoritative entry point is ``python3 -m apps.backend``.  This launcher
preserves the prior local command and its legacy runtime paths until MT-003
migrates the Web client and MT-005 retires legacy launch points.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_DIR = Path(__file__).resolve().parent


def _set_legacy_defaults() -> None:
    os.environ.setdefault("CURATOR_DATABASE_PATH", str(REPO_ROOT / "database" / "Curator.db"))
    os.environ.setdefault("CURATOR_CONFIG_PATH", str(LEGACY_DIR / "app_config.json"))
    os.environ.setdefault("CURATOR_LOG_DIR", str(LEGACY_DIR / "logs"))
    os.environ.setdefault("CURATOR_BACKUP_DIR", str(LEGACY_DIR / "backups"))


def main() -> None:
    _set_legacy_defaults()
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from apps.backend.server import main as backend_main

    backend_main()


if __name__ == "__main__":
    main()
