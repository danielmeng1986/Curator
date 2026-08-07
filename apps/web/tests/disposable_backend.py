"""Disposable Backend composition root for browser acceptance tests."""
from __future__ import annotations

import argparse
import signal
import threading
import sys
from pathlib import Path
from http.server import HTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.backend.tests.test_api_contract import _make_test_db
from apps.backend import server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--secret", required=True)
    args = parser.parse_args()
    database = _make_test_db()
    server.open_db = lambda: database
    server.AUTH_REGISTRATION_SECRET = args.secret
    server.DATABASE_PATH = type("DisposablePath", (), {"exists": lambda _: True, "__str__": lambda _: ":memory:"})()
    httpd = HTTPServer(("127.0.0.1", args.port), server.AppHandler)
    print(httpd.server_address[1], flush=True)
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown, daemon=True).start())
    httpd.serve_forever()
    database.close()


if __name__ == "__main__":
    main()
