"""Create expired/revoked Token states in disposable browser fixtures only."""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--token-uuid", required=True)
    parser.add_argument("--state", choices=("expired", "revoked"), required=True)
    args = parser.parse_args()
    database = Path(args.database).resolve()
    if "curator-browser-" not in str(database) or database.name != "Curator-Browser-Sandbox.db":
        raise ValueError("Token-state setup is restricted to disposable browser fixtures.")
    now = datetime.now(timezone.utc)
    connection = sqlite3.connect(database)
    try:
        if args.state == "expired":
            cursor = connection.execute(
                "UPDATE auth_token SET expires_at = ? WHERE uuid = ?",
                ((now - timedelta(minutes=1)).isoformat(), args.token_uuid),
            )
        else:
            cursor = connection.execute(
                "UPDATE auth_token SET revoked_at = ? WHERE uuid = ?",
                (now.isoformat(), args.token_uuid),
            )
        if cursor.rowcount != 1:
            raise ValueError("Fixture Token was not found.")
        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
