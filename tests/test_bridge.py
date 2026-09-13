from pathlib import Path

from lemove_code import bridge


def test_build_message_includes_correlation_metadata(tmp_path: Path):
    message = bridge.build_message(
        "corrija", request_id="req123", session_id="sess123", project_dir=tmp_path
    )
    assert "corrija" in message
    assert "request_id=req123" in message
    assert "session_id=sess123" in message
    assert str(tmp_path.resolve()) in message
    assert message.endswith("[Lemocode]")


def test_atomic_write(tmp_path: Path):
    target = tmp_path / "nested" / "value.txt"
    bridge._atomic_write(target, "olá")
    assert target.read_text(encoding="utf-8") == "olá"
    assert not list(target.parent.glob("*.tmp"))


def test_correlated_outbox_does_not_consume_another_response(tmp_path: Path, monkeypatch):
    outbox = tmp_path / "outbox"
    monkeypatch.setattr(bridge, "OUTBOX_DIR", outbox)
    monkeypatch.setattr(bridge, "BRIDGE_DIR", tmp_path)
    outbox.mkdir()
    bridge._atomic_write(
        outbox / "other.json",
        '{"requestId":"other","content":"outra resposta"}',
    )
    assert bridge.poll_response_once("expected") is None
    assert (outbox / "other.json").exists()
    bridge._atomic_write(
        outbox / "expected.json",
        '{"requestId":"expected","content":"resposta certa"}',
    )
    assert bridge.poll_response_once("expected") == "resposta certa"
    assert (outbox / "other.json").exists()
