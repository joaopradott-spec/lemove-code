"""
lemove_code.app  v1.0.0
------------------------
Interface estilo OpenCode usando Textual.
CSS definido como DEFAULT_CSS (atributo de classe) — compatível com
Textual 0.60+ inclusive no Python 3.14 no Windows.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from . import bridge
from .session_store import SessionStore

# ── Sessões ───────────────────────────────────────────────────────────────

# Segundos sem resposta antes de sugerir o botao Continuar do Claude.
STALL_NUDGE_S = 120

DATA_DIR = Path(os.environ.get("LEMOVE_DATA_DIR", Path.home() / ".lemove-code"))
SESSIONS_FILE = DATA_DIR / "sessions.json"
_SESSION_STORE: SessionStore | None = None


def _store() -> SessionStore:
    global _SESSION_STORE
    if _SESSION_STORE is None:
        _SESSION_STORE = SessionStore(DATA_DIR / "sessions.db")
        _SESSION_STORE.import_json_once(SESSIONS_FILE)
    return _SESSION_STORE


def _load_sessions() -> list[dict]:
    return _store().list_sessions()


def _save_sessions(sessions: list[dict]) -> None:
    for session in sessions:
        _store().save_session(session)


def _new_session(project_dir: Path) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "title": f"Sessao {datetime.now().strftime('%d/%m %H:%M')}",
        "project": str(project_dir),
        "created": datetime.now().isoformat(),
        "messages": [],
    }


def _short_path(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~") if s.startswith(home) else s


# ── Tela de ajuda ─────────────────────────────────────────────────────────

HELP_TEXT = """\
[bold #c792ff]Lemove Code — Atalhos[/]

[bold]Slash commands[/]
  /new       Nova sessao
  /clear     Limpar chat
  /sessions  Trocar sessao
  /rename X  Renomear sessao atual
  /delete CONFIRM  Excluir sessao atual
   /help      Esta tela
   /exit      Sair
   /janela    Restaurar janela do Claude

[bold]Prefixos[/]
  !cmd       Executa no terminal
  @arquivo   Insere arquivo na mensagem

[bold]Teclado[/]
   Ctrl+N     Nova sessao
   Ctrl+G     Cancelar espera
   Ctrl+O     Restaurar janela do Claude
   Ctrl+C     Sair

[bold]Botoes[/]
   Restaurar janela   Traz a janela do Claude de volta
   Colar              Cola o clipboard no campo de mensagem

[dim]Pressione qualquer tecla para fechar[/]
"""


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        background: #17171f;
        border: round #c792ff;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(HELP_TEXT, markup=True)

    def on_key(self, _event) -> None:
        self.dismiss()


# ── Tela de sessoes ───────────────────────────────────────────────────────

class SessionsScreen(ModalScreen):
    DEFAULT_CSS = """
    SessionsScreen {
        align: center middle;
    }
    #sess-box {
        background: #17171f;
        border: round #c792ff;
        padding: 1 2;
        width: 50;
        height: auto;
        max-height: 20;
    }
    """

    def __init__(self, sessions: list[dict], current_id: str) -> None:
        super().__init__()
        self._sessions = sessions
        self._current_id = current_id

    def compose(self) -> ComposeResult:
        items = []
        for s in self._sessions:
            marker = "[bold #c792ff]> [/]" if s["id"] == self._current_id else "  "
            item = ListItem(Label(f"{marker}{s['title']}  [{s['id']}]", markup=True))
            item.session_id = s["id"]
            items.append(item)
        with Vertical(id="sess-box"):
            yield Static("[bold #c792ff]Sessoes[/]\n", markup=True)
            yield ListView(*items, id="sessions-lv")
            yield Static("\n[dim]Enter abre  Esc fecha[/]", markup=True)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.dismiss(getattr(event.item, "session_id", None))

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ── ChatBubble ────────────────────────────────────────────────────────────

class ChatBubble(Static):
    def __init__(self, sender: str, text: str, kind: str = "assistant") -> None:
        css_class = {
            "user":      "bubble-user",
            "assistant": "bubble-assistant",
            "system":    "bubble-system",
            "error":     "bubble-error",
            "bash":      "bubble-bash",
        }.get(kind, "bubble-assistant")

        stamp = datetime.now().strftime("%H:%M")
        if kind == "user":
            content = f"[bold #d9f99d]VOCÊ[/]  [#65758b]{stamp}[/]\n{text}"
        elif kind == "assistant":
            content = f"[bold #a78bfa]{sender.upper()}[/]  [#65758b]{stamp}[/]\n{text}"
        elif kind == "error":
            content = f"[bold #ff6b6b]Erro[/]\n{text}"
        else:
            content = text

        super().__init__(content, classes=css_class, markup=True)


# ── Splash ────────────────────────────────────────────────────────────────

class SplashScreen(Screen):
    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
        background: #0d0d12;
    }
    #splash-content {
        width: 62;
        height: auto;
        content-align: center middle;
        background: #11131a;
        border: round #343846;
        padding: 2 4;
    }
    """

    AUTO_ADVANCE = 2.0

    def compose(self) -> ComposeResult:
        from . import __version__
        yield Static(
            "[#8b5cf6]     ╭─╮[/]\n"
            "[#a78bfa]  ╭──╯ ╰──╮[/]\n"
            "[#c4b5fd]  ╰──╮ ╭──╯[/]\n"
            "[#ddd6fe]     ╰─╯[/]\n\n"
            "[bold #f4f4f5]LEMOVE[/] [bold #a78bfa]CODE[/]\n"
            "[#8b93a7]Seu workspace, movido por IA.[/]\n\n"
            f"[#596174]QUALQUER TECLA PARA ENTRAR   •   v{__version__}[/]",
            markup=True,
            id="splash-content",
        )

    def on_mount(self) -> None:
        self.set_timer(self.AUTO_ADVANCE, self._advance)

    def on_key(self, _event) -> None:
        self._advance()

    def _advance(self) -> None:
        if self.is_current:
            self.app.pop_screen()


# ── ChatScreen ────────────────────────────────────────────────────────────

class ChatScreen(Screen):
    DEFAULT_CSS = """
    ChatScreen {
        background: #090a0f;
        color: #e8e9ed;
    }

    #shell {
        width: 100%;
        height: 100%;
    }

    #sidebar {
        width: 29;
        min-width: 25;
        height: 100%;
        background: #101118;
        border-right: solid #252833;
        padding: 1 2;
    }

    #brand {
        height: 5;
        color: #f4f4f5;
    }

    .sidebar-label {
        height: 2;
        color: #646b7c;
        text-style: bold;
        padding-top: 1;
    }

    #project-card {
        height: auto;
        min-height: 3;
        background: #171923;
        color: #b8bdca;
        border-left: solid #8b5cf6;
        padding: 1;
    }

    #session-card {
        height: auto;
        min-height: 4;
        color: #9ca3b4;
        padding: 1;
    }

    #sidebar-spacer {
        height: 1fr;
    }

    #sidebar-help {
        height: auto;
        color: #596174;
        padding-bottom: 1;
    }

    #main {
        width: 1fr;
        height: 100%;
        background: #090a0f;
    }

    #app-header {
        width: 100%;
        height: 3;
        background: #0d0e14;
        border-bottom: solid #1d2029;
    }

    #app-title {
        width: 1fr;
        height: 3;
        color: #d9dce4;
        padding: 0 2;
        content-align: left middle;
    }

    #connection {
        width: auto;
        height: 3;
        color: #84cc16;
        padding: 0 1;
        content-align: right middle;
    }

    #restore-btn {
        width: 12;
        height: 3;
        background: transparent;
        color: #9ca3b4;
        border: none;
        margin-right: 1;
    }

    #restore-btn:hover, #restore-btn:focus {
        background: #222532;
        color: #f4f4f5;
    }

    #chat-scroll {
        width: 100%;
        height: 1fr;
        background: #090a0f;
        padding: 2 4 1 4;
    }

    .bubble-user {
        width: 88%;
        background: #1a1d27;
        color: #e8e9ed;
        border-left: solid #a3e635;
        padding: 1 2;
        margin: 0 0 1 6;
    }

    .bubble-assistant {
        width: 92%;
        background: #12141c;
        color: #e8e9ed;
        border-left: solid #8b5cf6;
        padding: 1 2;
        margin: 0 6 1 0;
    }

    .bubble-system {
        color: #687083;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    .bubble-error {
        background: #241418;
        color: #ff6b6b;
        border-left: solid #ff6b6b;
        padding: 1 2;
        margin: 0 6 1 0;
    }

    .bubble-bash {
        background: #101712;
        color: #a3e635;
        border-left: solid #4d7c0f;
        padding: 1 2;
        margin: 0 0 1 0;
    }

    #input-wrap {
        height: 5;
        background: #141620;
        border: round #353949;
        margin: 0 3;
        padding: 0 1;
    }

    #input-wrap:focus-within {
        border: round #8b5cf6;
    }

    #prompt-input {
        width: 1fr;
        height: 3;
        background: #141620;
        border: none;
        color: #f4f4f5;
    }

    #paste-btn {
        width: 9;
        height: 3;
        background: #242735;
        color: #aeb4c2;
        border: none;
    }

    #paste-btn:hover, #paste-btn:focus {
        background: #8b5cf6;
        color: #ffffff;
    }

    #bottom-line {
        height: 2;
        margin: 0 3;
    }

    #status-bar {
        width: 1fr;
        height: 2;
        color: #737b8c;
        padding: 0 1;
        content-align: left middle;
    }

    #status-bar.thinking { color: #fbbf24; }
    #status-bar.ready { color: #84cc16; }
    #status-bar.error { color: #fb7185; }

    #key-hints {
        width: auto;
        height: 2;
        color: #505769;
        padding: 0 1;
        content-align: right middle;
    }

    ChatScreen.-narrow #sidebar {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_session", "Nova sessao"),
        Binding("ctrl+g", "cancel_wait", "Cancelar"),
        Binding("ctrl+o", "restore_window", "Restaurar janela"),
    ]

    status_text: reactive[str] = reactive("pronto")
    status_kind: reactive[str] = reactive("ready")

    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = project_dir
        self._waiting = False
        self._cancel_requested = False
        self._sessions: list[dict] = _load_sessions()

        existing = [s for s in self._sessions if s["project"] == str(project_dir)]
        if existing:
            self._session = existing[-1]
        else:
            self._session = _new_session(project_dir)
            self._sessions.append(self._session)
            _save_sessions(self._sessions)

        self._project_files: list[str] = []

    # ── compose ───────────────────────────────────────────────────────── #

    def compose(self) -> ComposeResult:
        short = _short_path(self.project_dir)
        with Horizontal(id="shell"):
            with Vertical(id="sidebar"):
                yield Static(
                    "[#8b5cf6] ◆[/]  [bold #f4f4f5]LEMOVE[/]\n"
                    "    [bold #a78bfa]CODE[/] [#4c5364]v1.0[/]",
                    id="brand", markup=True,
                )
                yield Static("WORKSPACE", classes="sidebar-label")
                yield Static(
                    f"[bold #e4e4e7]{self.project_dir.name or short}[/]\n"
                    "[#626a7c]pasta ativa[/]",
                    id="project-card", markup=True,
                )
                yield Static("CONVERSA", classes="sidebar-label")
                yield Static(
                    f"[#a78bfa]●[/]  {self._session['title']}\n"
                    f"[#596174]{self._session['id'][:8]}[/]",
                    id="session-card", markup=True,
                )
                yield Static(id="sidebar-spacer")
                yield Static(
                    "[#737b8c]Ctrl+N[/] · Nova conversa\n"
                    "[#737b8c]Ctrl+O[/] · Abrir Claude\n"
                    "[#737b8c]/help[/]  · Ver atalhos",
                    id="sidebar-help", markup=True,
                )

            with Vertical(id="main"):
                with Horizontal(id="app-header"):
                    yield Static(
                        f"[bold]Conversa[/]  [#596174]/  {self._session['title']}[/]",
                        id="app-title", markup=True,
                    )
                    yield Static("● conectado", id="connection")
                    yield Button("↗ Claude", id="restore-btn")

                with VerticalScroll(id="chat-scroll"):
                    yield ChatBubble(
                        "",
                        "Pronto para trabalhar neste projeto. "
                        "Descreva o que você quer construir ou alterar.",
                        kind="system",
                    )

                with Horizontal(id="input-wrap"):
                    yield Input(
                        placeholder="Escreva uma mensagem ou mencione @arquivo...",
                        id="prompt-input",
                    )
                    yield Button("Colar", id="paste-btn")

                with Horizontal(id="bottom-line"):
                    yield Static(self._status_line(), id="status-bar")
                    yield Static("Enter enviar   ^G cancelar   ^O Claude", id="key-hints")

    def on_mount(self) -> None:
        bridge.ensure_bridge_dir()
        bridge.register_project(self.project_dir)
        self._load_project_files_bg()
        self._ensure_claude_bg()
        # Vigia infinita da caixa de entrada desde a abertura:
        # mesmo sem enviar nada, qualquer lemove_reply do Claude
        # (response.done) aparece sozinho no chat.
        self.set_interval(0.5, self._poll_spontaneous_inbox)
        self.query_one("#prompt-input", Input).focus()

    @work(thread=True)
    def _ensure_claude_bg(self) -> None:
        try:
            self.app.call_from_thread(setattr, self, "status_text", "abrindo Claude Desktop...")
            self.app.call_from_thread(setattr, self, "status_kind", "thinking")
            result = bridge.ensure_claude_running()
            if result == "started":
                self.app.call_from_thread(
                    self._add_bubble, "", "Claude Desktop aberto automaticamente.", "system")
            self.app.call_from_thread(setattr, self, "status_text", "pronto")
            self.app.call_from_thread(setattr, self, "status_kind", "ready")
        except bridge.BridgeError as e:
            self.app.call_from_thread(setattr, self, "status_text", "pronto")
            self.app.call_from_thread(setattr, self, "status_kind", "ready")
            self.app.call_from_thread(
                self._add_bubble, "", f"{e}", "system")

    # ── status ────────────────────────────────────────────────────────── #

    def _status_line(self) -> str:
        icons = {"ready": "●", "thinking": "◐", "error": "✖"}
        icon = icons.get(self.status_kind, "●")
        return f"{icon}  {self.status_text}    •    Claude Desktop"

    def watch_status_text(self, _o, _n) -> None:
        self._refresh_status()

    def watch_status_kind(self, _o, _n) -> None:
        self._refresh_status()

    def _refresh_status(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(self._status_line())
            bar.remove_class("thinking", "ready", "error")
            bar.add_class(self.status_kind)
        except Exception:
            pass

    # ── chat ──────────────────────────────────────────────────────────── #

    def _add_bubble(self, sender: str, text: str, kind: str, persist: bool = True) -> None:
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(sender, text, kind=kind))
            scroll.scroll_end(animate=False)
            if persist and kind in ("user", "assistant"):
                ts = datetime.now().isoformat()
                item = {"role": kind, "content": text, "ts": ts}
                self._session.setdefault("messages", []).append(item)
                _store().add_message(self._session["id"], kind, text, ts)
        except Exception:
            pass

    def action_clear_chat(self) -> None:
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.remove_children()
            self._add_bubble("", "Chat limpo.", kind="system")
        except Exception:
            pass

    # ── input ─────────────────────────────────────────────────────────── #

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""

        if not text:
            return

        if text.startswith("/"):
            self._handle_slash(text)
            return

        if text.startswith("!"):
            self._handle_bash(text[1:].strip())
            return

        if self._waiting:
            self._add_bubble("", "Ainda aguardando resposta anterior...", kind="system")
            return

        final_text = self._expand_file_refs(text)
        self._add_bubble("Voce", text, kind="user")
        # Trava já na thread da UI pra vigia de 0.5s não roubar a resposta.
        self._waiting = True
        self._send_and_wait(final_text)

    def _handle_slash(self, text: str) -> None:
        cmd = text.lower().split()[0]
        if cmd in ("/sair", "/exit", "/quit", "/q"):
            self.app.exit()
        elif cmd in ("/limpar", "/clear"):
            self.action_clear_chat()
        elif cmd in ("/new", "/nova"):
            self.action_new_session()
        elif cmd == "/sessions":
            self._open_sessions_modal()
        elif cmd in ("/rename", "/renomear"):
            title = text.partition(" ")[2].strip()
            if not title:
                self._add_bubble("", "Uso: /rename novo titulo", kind="system")
            else:
                self._session["title"] = title
                _store().rename(self._session["id"], title)
                self._add_bubble("", f"Sessao renomeada: {title}", kind="system")
        elif cmd in ("/delete", "/excluir"):
            confirmation = text.partition(" ")[2].strip()
            if confirmation != "CONFIRM":
                self._add_bubble("", "Use /delete CONFIRM para excluir a sessao atual.", kind="system")
            else:
                old_id = self._session["id"]
                _store().delete(old_id)
                self._sessions = [s for s in self._sessions if s["id"] != old_id]
                self.action_new_session()
                self._add_bubble("", "Sessao anterior excluida.", kind="system")
        elif cmd == "/help":
            self.app.push_screen(HelpScreen())
        elif cmd == "/janela":
            self.action_restore_window()
        else:
            self._add_bubble("", f"Comando desconhecido: {cmd}  (tente /help)", kind="system")

    def _handle_bash(self, cmd: str) -> None:
        if not cmd:
            return
        self._add_bubble("", f"$ {cmd}", kind="bash")
        self._run_bash_worker(cmd)

    @work(thread=True)
    def _run_bash_worker(self, cmd: str) -> None:
        import subprocess
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                cwd=str(self.project_dir), timeout=30,
            )
            output = (result.stdout + result.stderr).strip() or "(sem saida)"
        except subprocess.TimeoutExpired:
            output = "Timeout (30s)"
        except Exception as e:
            output = f"Erro: {e}"
        self.app.call_from_thread(self._add_bubble, "", output, "bash")

    # ── @arquivo ──────────────────────────────────────────────────────── #

    @work(thread=True)
    def _load_project_files_bg(self) -> None:
        try:
            IGNORE = {"node_modules", ".git", "__pycache__", ".venv", "dist", "build"}
            files = []
            for p in self.project_dir.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(self.project_dir))
                    if not any(part in rel for part in IGNORE):
                        files.append(rel)
            self._project_files = sorted(files)
        except Exception:
            self._project_files = []

    def _expand_file_refs(self, text: str) -> str:
        import re
        def replace_ref(m):
            fname = m.group(1)
            candidates = [f for f in self._project_files if f.endswith(fname) or fname in f]
            if candidates:
                fpath = self.project_dir / candidates[0]
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    return f"\n\n[Conteudo de {candidates[0]}]:\n```\n{content}\n```\n"
                except Exception:
                    pass
            return m.group(0)
        return re.sub(r"@([\w./\\-]+)", replace_ref, text)

    # ── IA ────────────────────────────────────────────────────────────── #

    @work(exclusive=True, thread=True)
    def _send_and_wait(self, user_text: str) -> None:
        request_id = bridge.new_request_id()
        message = bridge.build_message(
            user_text, request_id=request_id,
            session_id=self._session["id"], project_dir=self.project_dir,
        )
        bridge.clear_pending_signal(request_id)

        self.app.call_from_thread(setattr, self, "status_text", "enviando para o Claude Desktop...")
        self.app.call_from_thread(setattr, self, "status_kind", "thinking")
        self.app.call_from_thread(setattr, self, "_waiting", True)
        self._cancel_requested = False

        try:
            bridge.send_to_claude_desktop(message)
        except bridge.BridgeError as e:
            self.app.call_from_thread(self._on_error, str(e))
            return

        self.app.call_from_thread(setattr, self, "status_text", "pensando...  Ctrl+G cancela")

        response: str | None = None
        wait_start = time.monotonic()
        nudged = False
        while not self._cancel_requested:
            result = bridge.poll_response_once(request_id)
            if result is not None:
                response = result
                break
            if not nudged and time.monotonic() - wait_start > STALL_NUDGE_S:
                nudged = True
                self.app.call_from_thread(
                    self._add_bubble, "",
                    "Demorando... se o Claude parou no limite de ferramentas, "
                    "restaure a janela e clique Continuar.",
                    "system")
            time.sleep(0.25)

        if self._cancel_requested:
            self.app.call_from_thread(self._on_cancelled)
            return

        self.app.call_from_thread(self._on_response, response)

    def _on_response(self, text: str) -> None:
        self._waiting = False
        self.status_text = "pronto"
        self.status_kind = "ready"
        self._add_bubble("\u2316 Lemove Code", text or "(resposta vazia)", kind="assistant")

    def _poll_spontaneous_inbox(self) -> None:
        """Vigia infinita: roda a cada 0.5s desde a abertura, mesmo sem envio.
        Se _waiting=True, o loop de _send_and_wait já está consumindo —
        aqui a gente pula pra não roubar a resposta dele."""
        if self._waiting:
            return
        try:
            result = bridge.poll_response_once()
        except Exception:
            return
        if result is not None:
            self._on_response(result)

    def _on_error(self, msg: str) -> None:
        self._waiting = False
        self.status_text = "erro"
        self.status_kind = "error"
        self._add_bubble("Erro", msg, kind="error")

    def _on_cancelled(self) -> None:
        self._waiting = False
        self.status_text = "pronto"
        self.status_kind = "ready"
        self._add_bubble("", "Espera cancelada. Se o Claude ainda estiver gerando, aguarde terminar antes de enviar.", kind="system")

    # ── acoes ─────────────────────────────────────────────────────────── #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "restore-btn":
            self.action_restore_window()
        elif event.button.id == "paste-btn":
            self._paste_clipboard()

    def _paste_clipboard(self) -> None:
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception:
            self._add_bubble("Erro", "Nao consegui ler o clipboard.", "error")
            return
        if not text or not str(text).strip():
            self._add_bubble("", "Clipboard vazio.", "system")
            return
        try:
            inp = self.query_one("#prompt-input", Input)
            cur = inp.value
            try:
                pos = inp.cursor_position
            except Exception:
                pos = len(cur)
            pos = max(0, min(pos, len(cur)))
            inp.value = cur[:pos] + str(text) + cur[pos:]
            try:
                inp.cursor_position = pos + len(str(text))
            except Exception:
                pass
            inp.focus()
        except Exception as e:
            self._add_bubble("Erro", f"Nao consegui colar: {e}", "error")

    @work(thread=True)
    def _restore_window_bg(self) -> None:
        try:
            bridge.restore_claude_window()
            self.app.call_from_thread(
                self._add_bubble, "", "Janela do Claude Desktop restaurada.", "system")
        except bridge.BridgeError as e:
            self.app.call_from_thread(self._add_bubble, "Erro", str(e), "error")

    def action_restore_window(self) -> None:
        self._restore_window_bg()

    def action_cancel_wait(self) -> None:
        if self._waiting:
            self._cancel_requested = True

    def action_new_session(self) -> None:
        self._session = _new_session(self.project_dir)
        self._sessions.append(self._session)
        _save_sessions(self._sessions)
        self.action_clear_chat()
        self._refresh_status()
        self._add_bubble("", f"Nova sessao: {self._session['title']}", kind="system")

    def _open_sessions_modal(self) -> None:
        def _on_close(session_id):
            if not session_id:
                return
            matches = [s for s in self._sessions if s["id"] == session_id]
            if not matches:
                return
            self._session = matches[0]
            self.action_clear_chat()
            for m in self._session.get("messages", [])[-20:]:
                kind = m.get("role", "system")
                sender = "Voce" if kind == "user" else "\u2316 Lemove Code"
                self._add_bubble(sender, m.get("content", ""), kind=kind, persist=False)
            self._add_bubble("", f"Sessao carregada: {self._session['title']}", kind="system")
        self.app.push_screen(SessionsScreen(self._sessions, self._session["id"]), _on_close)


# ── App principal ─────────────────────────────────────────────────────────

class LemoveCodeApp(App):
    TITLE = "Lemove Code"

    DEFAULT_CSS = """
    LemoveCodeApp {
        background: #0d0d12;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Sair", priority=True),
    ]

    def __init__(self, project_dir: Path | None = None) -> None:
        super().__init__()
        self.project_dir = project_dir or Path.cwd()

    def on_mount(self) -> None:
        self.push_screen(ChatScreen(self.project_dir))
        self.push_screen(SplashScreen())


def run(project_dir: Path | None = None) -> None:
    LemoveCodeApp(project_dir=project_dir).run()
