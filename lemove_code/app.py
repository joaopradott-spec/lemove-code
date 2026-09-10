"""
lemove_code.app  v0.4.0-beta
------------------------
Interface estilo OpenCode usando Textual.
CSS definido como DEFAULT_CSS (atributo de classe) — compatível com
Textual 0.60+ inclusive no Python 3.14 no Windows.
"""

from __future__ import annotations

import json
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
from textual.widgets import Button, Footer, Input, Label, ListItem, ListView, Static

from . import bridge

# ── Sessões ───────────────────────────────────────────────────────────────

# Segundos sem resposta antes de sugerir o botao Continuar do Claude.
STALL_NUDGE_S = 120

SESSIONS_FILE = Path.home() / ".lemove-code" / "sessions.json"


def _load_sessions() -> list[dict]:
    try:
        return json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_sessions(sessions: list[dict]) -> None:
    try:
        SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SESSIONS_FILE.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _new_session(project_dir: Path) -> dict:
    return {
        "id": str(uuid.uuid4())[:8],
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

        if kind == "user":
            content = f"[bold #7ee787]Voce[/]\n{text}"
        elif kind == "assistant":
            content = f"[bold #c792ff]{sender}[/]\n{text}"
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
        width: auto;
        height: auto;
        content-align: center middle;
    }
    """

    AUTO_ADVANCE = 2.0

    def compose(self) -> ComposeResult:
        from . import __version__
        yield Static(
            f"[bold #c792ff]\u2316  Lemove Code[/]\n\n"
            f"[dim]Terminal de IA usando o Claude Desktop.[/]\n\n"
            f"[#3a3a4a]Pressione qualquer tecla para comecar...   v{__version__}[/]",
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
        background: #0d0d12;
        color: #e6e6ea;
    }

    #app-header {
        height: 1;
        background: #17171f;
        dock: top;
    }

    #app-title {
        width: 1fr;
        height: 1;
        background: #17171f;
        color: #c792ff;
        text-style: bold;
        padding: 0 2;
    }

    #restore-btn {
        width: auto;
        min-width: 18;
        height: 1;
        background: #3a3a4a;
        color: #e6e6ea;
        border: none;
    }

    #restore-btn:hover {
        background: #c792ff;
        color: #0d0d12;
    }

    #restore-btn:focus {
        background: #c792ff;
        color: #0d0d12;
    }

    #chat-scroll {
        background: #0d0d12;
        padding: 1 2;
    }

    .bubble-user {
        background: #1c2030;
        color: #e6e6ea;
        border-left: thick #3a3a4a;
        padding: 0 1;
        margin: 0 0 1 4;
    }

    .bubble-assistant {
        background: #14141b;
        color: #e6e6ea;
        border-left: thick #c792ff;
        padding: 0 1;
        margin: 0 4 1 0;
    }

    .bubble-system {
        color: #6c6c7c;
        text-style: italic;
        margin: 0 0 1 0;
        padding: 0 1;
    }

    .bubble-error {
        color: #ff6b6b;
        border-left: thick #ff6b6b;
        padding: 0 1;
        margin: 0 4 1 0;
    }

    .bubble-bash {
        background: #17171f;
        color: #7ee787;
        border-left: thick #7ee787;
        padding: 0 1;
        margin: 0 0 1 0;
    }

    #status-bar {
        height: 1;
        background: #17171f;
        color: #6c6c7c;
        padding: 0 2;
        dock: bottom;
    }

    #status-bar.thinking {
        color: #ffb454;
    }

    #status-bar.ready {
        color: #7ee787;
    }

    #status-bar.error {
        color: #ff6b6b;
    }

    #input-wrap {
        height: 3;
        background: #14141b;
        border: round #3a3a4a;
        margin: 0 1 1 1;
        dock: bottom;
    }

    #input-wrap:focus-within {
        border: round #c792ff;
    }

    #prompt-input {
        width: 1fr;
        background: #14141b;
        border: none;
        color: #e6e6ea;
    }

    #paste-btn {
        width: auto;
        min-width: 9;
        height: 1;
        background: #3a3a4a;
        color: #e6e6ea;
        border: none;
        margin: 0 1 0 0;
    }

    #paste-btn:hover {
        background: #c792ff;
        color: #0d0d12;
    }

    #paste-btn:focus {
        background: #c792ff;
        color: #0d0d12;
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

        with Horizontal(id="app-header"):
            yield Static(
                f"[\u2316] Lemove Code  {short}",
                id="app-title",
            )
            yield Button("Restaurar janela", id="restore-btn")

        with VerticalScroll(id="chat-scroll"):
            yield ChatBubble(
                "",
                f"Sessao: {self._session['title']}  |  {short}\n"
                "Digite sua mensagem.  /help para ver atalhos.",
                kind="system",
            )

        yield Static(self._status_line(), id="status-bar")

        with Horizontal(id="input-wrap"):
            yield Input(
                placeholder="Mensagem... (/help, !cmd, @arquivo)",
                id="prompt-input",
            )
            yield Button("Colar", id="paste-btn")

        yield Footer()

    def on_mount(self) -> None:
        bridge.ensure_bridge_dir()
        self._load_project_files_bg()
        self._ensure_claude_bg()
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
        sid = self._session["id"]
        return f" {icon}  {self.status_text}    sessao:{sid}  claude-desktop"

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

    def _add_bubble(self, sender: str, text: str, kind: str) -> None:
        try:
            scroll = self.query_one("#chat-scroll", VerticalScroll)
            scroll.mount(ChatBubble(sender, text, kind=kind))
            scroll.scroll_end(animate=False)
            if kind in ("user", "assistant"):
                self._session.setdefault("messages", []).append(
                    {"role": kind, "content": text, "ts": datetime.now().isoformat()}
                )
                _save_sessions(self._sessions)
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
        message = bridge.build_message(user_text)
        bridge.clear_pending_signal()

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
            result = bridge.poll_response_once()
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
                self._add_bubble(sender, m.get("content", ""), kind=kind)
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
