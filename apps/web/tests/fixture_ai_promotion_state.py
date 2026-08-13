#!/usr/bin/env python3
"""Read the durable outcome of a disposable AI Promotion fixture."""
from __future__ import annotations

import argparse
import json
import sqlite3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--album-id", required=True, type=int)
    args = parser.parse_args()
    connection = sqlite3.connect(args.database)
    connection.row_factory = sqlite3.Row
    album = connection.execute(
        """SELECT a.id, a.title, s.name AS status_name
           FROM album a LEFT JOIN status s ON s.id=a.status_id WHERE a.id=?""",
        (args.album_id,),
    ).fetchone()
    result = {
        "album": dict(album) if album else None,
        "promotions": connection.execute(
            "SELECT COUNT(*) FROM workspace_album_name_promotion WHERE album_id=? AND outcome='Promoted'",
            (args.album_id,),
        ).fetchone()[0],
        "promotion_operations": connection.execute(
            """SELECT COUNT(*) FROM operation o JOIN album a ON a.uuid=o.entity_uuid
               WHERE a.id=? AND o.operation_type='workspace_promotion' AND o.status='Succeeded'""",
            (args.album_id,),
        ).fetchone()[0],
        "approved_reviews": connection.execute(
            """SELECT COUNT(*) FROM ai_work_item_review r
               JOIN workspace_album_ai_worker i ON i.uuid=r.work_item_uuid
               WHERE i.album_id=? AND r.state='Approved'""",
            (args.album_id,),
        ).fetchone()[0],
        "result_stages": connection.execute(
            """SELECT COUNT(*) FROM ai_work_item_result_stage r
               JOIN workspace_album_ai_worker i ON i.uuid=r.work_item_uuid
               WHERE i.album_id=?""",
            (args.album_id,),
        ).fetchone()[0],
        "reservations": connection.execute(
            "SELECT COUNT(*) FROM album_work_reservation WHERE album_id=?",
            (args.album_id,),
        ).fetchone()[0],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
