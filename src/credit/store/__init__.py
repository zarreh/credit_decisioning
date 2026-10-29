"""SQLite store for the review queue, its audit events and analyst report drafts.

Every state change is one conditional UPDATE inside a transaction, keyed on the
expected status and revision, so a double click or a stale page gets a clean conflict
instead of a second decision (guide Part A). The event log is append-only.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    application TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    record TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_by_application ON events (application_id, seq);
CREATE TABLE IF NOT EXISTS report_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Conflict(Exception):
    """The row was not in the expected status/revision."""


class Store:
    def __init__(self, path: str) -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def rebuild(self, items: Sequence[tuple[str, dict[str, Any]]]) -> None:
        """Destructive reset: one transaction, all rows replaced, all history cleared."""
        stamp = now()
        with self._tx() as conn:
            conn.execute("DELETE FROM applications")
            conn.execute("DELETE FROM events")
            conn.executemany(
                "INSERT INTO applications (id, application, status, created_at, updated_at) "
                "VALUES (?, ?, 'queued', ?, ?)",
                [(i, json.dumps(a), stamp, stamp) for i, a in items],
            )

    def get(self, app_id: str) -> dict[str, Any] | None:
        with self._tx() as conn:
            row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
        return _decode(row) if row else None

    def all(self) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute("SELECT * FROM applications ORDER BY id").fetchall()
        return [_decode(r) for r in rows]

    def transition(
        self,
        app_id: str,
        from_status: Sequence[str],
        revision: int,
        to_status: str,
        record: dict[str, Any],
        events: Sequence[tuple[str, str, dict[str, Any]]],
    ) -> None:
        """Move one row atomically; raise Conflict if status or revision moved on."""
        marks = ",".join("?" * len(from_status))
        with self._tx() as conn:
            cur = conn.execute(
                f"UPDATE applications SET status = ?, revision = revision + 1, record = ?, "  # noqa: S608
                f"updated_at = ? WHERE id = ? AND revision = ? AND status IN ({marks})",
                (to_status, json.dumps(record), now(), app_id, revision, *from_status),
            )
            if cur.rowcount != 1:
                raise Conflict(app_id)
            conn.executemany(
                "INSERT INTO events (application_id, kind, actor, detail, at) VALUES (?, ?, ?, ?, ?)",
                [(app_id, kind, actor, json.dumps(detail), now()) for kind, actor, detail in events],
            )

    def events(self, app_id: str) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute(
                "SELECT seq, kind, actor, detail, at FROM events WHERE application_id = ? ORDER BY seq",
                (app_id,),
            ).fetchall()
        return [dict(r) | {"detail": json.loads(r["detail"])} for r in rows]

    def add_draft(self, kind: str, title: str, body: str) -> int:
        with self._tx() as conn:
            cur = conn.execute(
                "INSERT INTO report_drafts (kind, title, body, status, created_at) VALUES (?, ?, ?, 'draft', ?)",
                (kind, title, body, now()),
            )
        return int(cur.lastrowid or 0)

    def drafts(self) -> list[dict[str, Any]]:
        with self._tx() as conn:
            rows = conn.execute("SELECT * FROM report_drafts ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    out["application"] = json.loads(out["application"])
    out["record"] = json.loads(out["record"])
    return out
