#!/usr/bin/env python3
import json
import sqlite3
import socket
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
DATABASE_PATH = REPO_ROOT / "database" / "Curator.db"
QUERY_DIR = REPO_ROOT / "database"
LOG_PATH = BASE_DIR / "logs" / "changes.log"

ALLOWED_TABLES = {"workspace_album"}
EXCLUDED_QUERY_FILES = {"Curator.db"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def get_table_schema(table_name: str) -> list[dict]:
    with open_db() as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": bool(row["notnull"]),
            "default": row["dflt_value"],
            "pk": bool(row["pk"]),
        }
        for row in rows
    ]


def list_query_files() -> list[dict]:
    queries: list[dict] = []
    if not QUERY_DIR.exists():
        return queries

    for path in sorted(QUERY_DIR.iterdir()):
        if not path.is_file() or path.name in EXCLUDED_QUERY_FILES:
            continue
        try:
            sql = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            continue

        if not sql:
            continue
        queries.append({"name": path.name, "sql": sql})

    return queries


def load_query_sql(query_name: str) -> str:
    if not query_name:
        raise ValueError("query_name is required")
    if "/" in query_name or ".." in query_name:
        raise ValueError("invalid query_name")

    query_path = QUERY_DIR / query_name
    if not query_path.exists() or not query_path.is_file():
        raise ValueError(f"query file not found: {query_name}")
    if query_path.name in EXCLUDED_QUERY_FILES:
        raise ValueError("query file is not allowed")

    sql = query_path.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError("query file is empty")

    normalized = sql.lstrip().lower()
    if not normalized.startswith("select"):
        raise ValueError("only SELECT statements are supported")
    return sql


def query_rows(sql: str) -> tuple[list[str], list[dict]]:
    with open_db() as conn:
        cur = conn.execute(sql)
        columns = [desc[0] for desc in (cur.description or [])]
        rows = [dict(row) for row in cur.fetchall()]
    return columns, rows


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            # Client disconnected while response was in flight.
            return

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "database_path": str(DATABASE_PATH),
                    "server_time": utc_now_iso(),
                },
            )
            return

        if parsed.path == "/api/queries":
            self._send_json(200, {"ok": True, "queries": list_query_files()})
            return

        if parsed.path == "/api/schema":
            qs = parse_qs(parsed.query)
            table_name = (qs.get("table") or ["workspace_album"])[0]
            if table_name not in ALLOWED_TABLES:
                self._send_json(400, {"ok": False, "error": "table is not allowed"})
                return
            schema = get_table_schema(table_name)
            self._send_json(200, {"ok": True, "table": table_name, "schema": schema})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json body"})
            return

        if parsed.path == "/api/run-query":
            query_name = str(body.get("query_name", "")).strip()
            try:
                sql = load_query_sql(query_name)
                columns, rows = query_rows(sql)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "query_name": query_name,
                        "sql": sql,
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                    },
                )
            except Exception as ex:
                self._send_json(400, {"ok": False, "error": str(ex)})
            return

        if parsed.path == "/api/batch-update":
            table_name = str(body.get("table", "workspace_album")).strip()
            pk_column = str(body.get("pk_column", "id")).strip()
            updates = body.get("updates", [])

            if table_name not in ALLOWED_TABLES:
                self._send_json(400, {"ok": False, "error": "table is not allowed"})
                return

            if not isinstance(updates, list) or not updates:
                self._send_json(400, {"ok": False, "error": "updates must be a non-empty list"})
                return

            schema = get_table_schema(table_name)
            schema_names = {col["name"] for col in schema}
            pk_schema = next((col for col in schema if col["pk"]), None)

            if pk_schema is None:
                self._send_json(400, {"ok": False, "error": "table has no primary key"})
                return

            real_pk_column = pk_schema["name"]
            if pk_column != real_pk_column:
                self._send_json(400, {"ok": False, "error": f"pk_column must be {real_pk_column}"})
                return

            invalid_columns = []
            for item in updates:
                changes = item.get("changes", {})
                if not isinstance(changes, dict):
                    invalid_columns.append("<invalid changes payload>")
                    continue
                for col in changes.keys():
                    if col == pk_column or col not in schema_names:
                        invalid_columns.append(col)

            if invalid_columns:
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "error": "invalid columns in changes",
                        "columns": sorted(set(invalid_columns)),
                    },
                )
                return

            results: list[dict] = []
            changed_total = 0
            update_errors: list[str] = []

            try:
                with open_db() as conn:
                    conn.execute("BEGIN")
                    for idx, item in enumerate(updates, start=1):
                        pk_value = item.get("pk_value")
                        changes = item.get("changes", {})

                        if pk_value is None:
                            raise ValueError(f"row #{idx}: pk_value is required")
                        if not isinstance(changes, dict) or not changes:
                            continue

                        before = conn.execute(
                            f"SELECT * FROM {table_name} WHERE {pk_column} = ?",
                            (pk_value,),
                        ).fetchone()
                        if before is None:
                            raise ValueError(f"row #{idx}: record with {pk_column}={pk_value} not found")

                        set_columns = [col for col in changes.keys() if col != pk_column]
                        if not set_columns:
                            continue

                        set_expr = ", ".join([f"{col} = ?" for col in set_columns])
                        values = [changes[col] for col in set_columns]
                        values.append(pk_value)

                        conn.execute(
                            f"UPDATE {table_name} SET {set_expr} WHERE {pk_column} = ?",
                            values,
                        )

                        after = conn.execute(
                            f"SELECT * FROM {table_name} WHERE {pk_column} = ?",
                            (pk_value,),
                        ).fetchone()

                        before_dict = dict(before)
                        after_dict = dict(after) if after is not None else {}
                        changed_fields = {
                            col: {"before": before_dict.get(col), "after": after_dict.get(col)}
                            for col in set_columns
                            if before_dict.get(col) != after_dict.get(col)
                        }
                        if changed_fields:
                            changed_total += 1
                            results.append(
                                {
                                    "pk_value": pk_value,
                                    "changed_fields": changed_fields,
                                }
                            )

                    conn.commit()
            except Exception as ex:
                update_errors.append(str(ex))

            log_entry = {
                "timestamp": utc_now_iso(),
                "table": table_name,
                "pk_column": pk_column,
                "requested_updates": len(updates),
                "applied_updates": changed_total,
                "success": not update_errors,
                "errors": update_errors,
                "results": results,
            }
            append_log(log_entry)

            if update_errors:
                self._send_json(
                    500,
                    {
                        "ok": False,
                        "error": "batch update failed",
                        "details": update_errors,
                    },
                )
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "message": "batch update succeeded",
                    "applied_updates": changed_total,
                    "results": results,
                    "log_path": str(LOG_PATH),
                },
            )
            return

        self._send_json(404, {"ok": False, "error": "endpoint not found"})


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    if not STATIC_DIR.exists():
        raise FileNotFoundError(f"Static directory not found: {STATIC_DIR}")

    host = "127.0.0.1"
    port = 8787
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Curator Normalize App running at http://{host}:{port}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Logs: {LOG_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
