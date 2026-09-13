from pathlib import Path

from lemove_code import app as app_module


async def test_tui_starts_headless(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(app_module, "SESSIONS_FILE", tmp_path / "data" / "sessions.json")
    monkeypatch.setattr(app_module, "_SESSION_STORE", None)
    monkeypatch.setattr(app_module.bridge, "ensure_claude_running", lambda: "already")
    monkeypatch.setattr(app_module.bridge, "register_project", lambda _path: None)
    application = app_module.LemoveCodeApp(project_dir=tmp_path)
    async with application.run_test(size=(100, 35)) as pilot:
        await pilot.press("x")
        await pilot.pause()
        assert application.screen.query_one("#prompt-input").placeholder
        assert application.screen.query_one("#project-card")
