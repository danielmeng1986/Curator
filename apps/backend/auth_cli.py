"""Local-console authentication administration commands."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from . import repositories as repo
from . import server
from . import services as svc


def _database_factory(database_path: Path):
    def connect():
        connection = sqlite3.connect(database_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    return connect


def _bootstrap_admin(args: argparse.Namespace) -> int:
    database_path = Path(args.database or server.DATABASE_PATH).expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    factory = _database_factory(database_path)
    auth = svc.AuthenticationService(
        repo.AuthRepository(factory),
        operation_service=svc.OperationService(repo.OperationRepository(factory)),
    )
    try:
        issued = auth.bootstrap_first_admin(
            device_name=args.device_name,
            device_identity=args.device_identity,
        )
    except (svc.ServiceConflict, ValueError) as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 2
    print("Initial administrator created.")
    print(f"Device: {issued['registration']['device_name']}")
    print(f"Expires: {issued['token_record']['expires_at']}")
    print("Admin Token (shown once):")
    print(issued["token"])
    print("Store this Token securely. It cannot be displayed again.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m apps.backend")
    subcommands = parser.add_subparsers(dest="command")
    auth = subcommands.add_parser("auth", help="Local authentication administration")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    bootstrap = auth_commands.add_parser("bootstrap-admin", help="Create the first administrator")
    bootstrap.add_argument("--device-name", required=True)
    bootstrap.add_argument("--device-identity", required=True)
    bootstrap.add_argument("--database", help="Explicit database path; defaults to configured Curator database")
    bootstrap.set_defaults(handler=_bootstrap_admin)
    return parser


def main(argv: list[str] | None = None) -> int | None:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        return None
    parser = build_parser()
    args = parser.parse_args(args_list)
    if not hasattr(args, "handler"):
        parser.error("a command is required")
    return args.handler(args)
