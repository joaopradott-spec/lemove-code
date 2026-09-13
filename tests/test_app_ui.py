import os
import tempfile
from pathlib import Path

import pytest
from textual.widgets import Static

# app.py inicializa o banco de sessões no diretório do usuário ao importar.
os.environ["USERPROFILE"] = tempfile.mkdtemp(prefix="lemove-ui-test-")

from lemove_code import app as app_module


@pytest.mark.asyncio
async def test_chat_screen_renders_new_shell(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app_module.bridge, "ensure_bridge_dir", lambda: None)
    monkeypatch.setattr(app_module.bridge, "register_project", lambda _path: None)
    monkeypatch.setattr(app_module.ChatScreen, "_ensure_claude_bg", lambda self: None)

    application = app_module.LemoveCodeApp(tmp_path)
    async with application.run_test(size=(120, 35)) as pilot:
        await pilot.press("x")
        await pilot.pause()

        assert isinstance(application.screen, app_module.ChatScreen)
        assert application.screen.query_one("#app-title", Static)
        assert application.screen.query_one("#project-card", Static)
        assert application.screen.query_one("#sidebar", app_module.Vertical)
        assert application.screen.query_one("#prompt-input").placeholder.startswith("Escreva")
