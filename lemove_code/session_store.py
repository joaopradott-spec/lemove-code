"""Persistencia transacional das sessoes do Lemove Code."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path


class SessionStore:
    """SQLite evita corrupcao e duplicacao do antigo sessions.json."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, project TEXT NOT NULL,
                    created TEXT NOT NULL, updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL, ts TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project, updated);
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);
                """
            )
            db.commit()

    def import_json_once(self, legacy_path: Path) -> None:
        marker = self.path.with_suffix(".migrated")
        if marker.exists() or not legacy_path.exists():
            return
        try:
            items = json.loads(legacy_path.read_text(encoding="utf-8"))
            for session in items if isinstance(items, list) else []:
                self.save_session(session)
                for msg in session.get("messages", []):
                    self.add_message(session["id"], msg.get("role", "system"),
                                     msg.get("content", ""), msg.get("ts", session["created"]))
            marker.write_text("ok", encoding="utf-8")
        except Exception:
            pass

    def list_sessions(self, project: str | None = None) -> list[dict]:
        sql = "SELECT * FROM sessions"
        params: tuple[str, ...] = ()
        if project is not None:
            sql += " WHERE project = ?"
            params = (project,)
        sql += " ORDER BY updated"
        with closing(self._connect()) as db:
            rows = db.execute(sql, params).fetchall()
            return [dict(row) | {"messages": self.messages(row["id"])} for row in rows]

    def save_session(self, session: dict) -> None:
        updated = session.get("updated", session["created"])
        with closing(self._connect()) as db:
            db.execute(
                "INSERT INTO sessions(id,title,project,created,updated) VALUES(?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET title=excluded.title, project=excluded.project, updated=excluded.updated",
                (session["id"], session["title"], session["project"], session["created"], updated),
            )
            db.commit()

    def add_message(self, session_id: str, role: str, content: str, ts: str) -> None:
        with closing(self._connect()) as db:
            db.execute("INSERT INTO messages(session_id,role,content,ts) VALUES(?,?,?,?)",
                       (session_id, role, content, ts))
            db.execute("UPDATE sessions SET updated=? WHERE id=?", (ts, session_id))
            db.commit()

    def messages(self, session_id: str, limit: int | None = None) -> list[dict]:
        sql = "SELECT role,content,ts FROM messages WHERE session_id=? ORDER BY id"
        params: tuple[object, ...] = (session_id,)
        if limit:
            sql = "SELECT role,content,ts FROM (SELECT * FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?) ORDER BY id"
            params = (session_id, limit)
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def rename(self, session_id: str, title: str) -> None:
        with closing(self._connect()) as db:
            db.execute("UPDATE sessions SET title=? WHERE id=?", (title.strip(), session_id))
            db.commit()

    def delete(self, session_id: str) -> None:
        with closing(self._connect()) as db:
            db.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            db.commit()
