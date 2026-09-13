from datetime import datetime
from pathlib import Path

from lemove_code.session_store import SessionStore


def test_session_roundtrip_does_not_duplicate(tmp_path: Path):
    store = SessionStore(tmp_path / "sessions.db")
    now = datetime.now().isoformat()
    session = {"id": "abc", "title": "Teste", "project": str(tmp_path), "created": now}
    store.save_session(session)
    store.add_message("abc", "user", "uma vez", now)

    first = store.list_sessions(str(tmp_path))[0]
    second = store.list_sessions(str(tmp_path))[0]
    assert first["messages"] == second["messages"]
    assert len(second["messages"]) == 1


def test_rename_and_delete(tmp_path: Path):
    store = SessionStore(tmp_path / "sessions.db")
    now = datetime.now().isoformat()
    store.save_session({"id": "abc", "title": "Antes", "project": "p", "created": now})
    store.rename("abc", "Depois")
    assert store.list_sessions()[0]["title"] == "Depois"
    store.delete("abc")
    assert store.list_sessions() == []
