"""
lemove_code.bridge
-------------------

Toda a lógica de "ponte" com o Claude Desktop: focar a janela certa
(ignorando abas de navegador), colar a mensagem, e depois vigiar o
arquivo de resposta que o Claude Desktop escreve.

Isolado do módulo de UI (app.py) para que a TUI só precise chamar
funções simples e assíncronas.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

# Pasta onde o arquivo de "ponte" fica. O Claude Desktop escreve aqui,
# o CLI lê daqui.
BRIDGE_DIR = Path.home() / ".lemove-code"
RESPONSE_FILE = BRIDGE_DIR / "response.txt"
SIGNAL_FILE = BRIDGE_DIR / "response.done"  # marcador de "terminei de escrever"

TRIGGER_WORD = "Lemocode"
HIDDEN_INSTRUCTION = "\n\n[{trigger}]"

# Nomes de processo de navegadores conhecidos — janelas pertencentes a
# esses processos são ignoradas, mesmo que o título contenha "Claude"
# (ex: uma aba aberta em claude.ai).
BROWSER_PROCESS_NAMES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "opera_gx.exe", "vivaldi.exe", "iexplore.exe",
}

# Nome do processo do app oficial Claude Desktop no Windows.
CLAUDE_DESKTOP_PROCESS_NAME = "claude.exe"


class BridgeError(Exception):
    """Erro de alto nível para qualquer falha ao falar com o Claude Desktop."""


def ensure_bridge_dir() -> None:
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)


def build_message(user_text: str) -> str:
    """Monta a mensagem real enviada ao Claude Desktop, com a palavra-gatilho
    que ativa a regra configurada nas Instructions for Claude."""
    return user_text + HIDDEN_INSTRUCTION.format(trigger=TRIGGER_WORD)


def _get_process_name_for_window(win) -> Optional[str]:
    """Retorna o nome do processo (ex: 'claude.exe') dono da janela dada,
    ou None se não conseguir determinar (ex: rodando fora do Windows)."""
    try:
        import win32process
        import psutil

        _, pid = win32process.GetWindowThreadProcessId(win._hWnd)
        proc = psutil.Process(pid)
        return proc.name().lower()
    except Exception:
        return None


def find_claude_desktop_window(gw):
    """Procura, entre as janelas com 'Claude' no título, a que pertence
    de fato ao processo do app Desktop — ignorando abas de navegador."""
    candidates = gw.getWindowsWithTitle("Claude")
    if not candidates:
        return None

    for win in candidates:
        process_name = _get_process_name_for_window(win)

        if process_name is None:
            # Não foi possível confirmar o processo (ex: pywin32 ausente).
            # Como fallback, aceita a janela apenas se o título não bater
            # com padrões óbvios de navegador.
            title_lower = win.title.lower()
            if any(b in title_lower for b in ("chrome", "edge", "firefox", "opera", "brave")):
                continue
            return win

        if process_name in BROWSER_PROCESS_NAMES:
            continue  # é uma aba de navegador, ignora
        if process_name == CLAUDE_DESKTOP_PROCESS_NAME:
            return win

    return None


def _get_foreground_window_handle() -> Optional[int]:
    """Pega o handle da janela em foco no momento (deve ser o terminal
    de onde o usuário chamou o lemovecode), para poder devolver o foco
    a ela depois de mexer no Claude Desktop."""
    try:
        import win32gui

        return win32gui.GetForegroundWindow()
    except Exception:
        return None


def _restore_foreground_window(handle: Optional[int]) -> None:
    """Devolve o foco de teclado para a janela do terminal. Sem isso,
    depois de ativar o Claude Desktop (mesmo fora da tela) o Windows
    deixa o foco nele, e o usuário precisa clicar de volta no terminal
    manualmente para continuar digitando."""
    if handle is None:
        return
    try:
        import win32gui
        import win32con

        if win32gui.IsIconic(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(handle)
    except Exception:
        pass  # não é fatal — pior caso o usuário clica de volta manualmente


def send_to_claude_desktop(message: str) -> None:
    """
    Move a janela do Claude Desktop para fora da área visível da tela,
    foca ela lá (sem aparecer pro usuário), cola a mensagem no campo de
    chat e envia — e por fim devolve o foco para o terminal de onde a
    chamada partiu.

    Filtra a janela pelo processo dono (Claude.exe), não só pelo título
    "Claude" — isso evita mandar a mensagem para uma aba de navegador
    aberta em claude.ai, que também teria "Claude" no título.

    Levanta BridgeError com uma mensagem amigável em caso de falha.
    """
    try:
        import pygetwindow as gw
        import pyautogui
        import pyperclip
    except (ImportError, NotImplementedError) as e:
        raise BridgeError(
            "Automação de janela não é suportada neste sistema. "
            "O Lemove Code precisa rodar no Windows, com uma sessão gráfica, "
            "onde o Claude Desktop está aberto."
        ) from e

    win = find_claude_desktop_window(gw)
    if win is None:
        raise BridgeError(
            "Não encontrei a janela do app Claude Desktop (só de navegador, "
            "ou nenhuma). Abra o app Claude Desktop de verdade e tente novamente."
        )

    # Guarda qual janela (o terminal) estava em foco ANTES de mexer no
    # Claude Desktop, para poder devolver o foco a ela no final.
    terminal_handle = _get_foreground_window_handle()

    try:
        if win.isMinimized:
            win.restore()
            time.sleep(0.3)
        # Move a janela para bem longe da área visível de qualquer monitor,
        # mantendo o mesmo tamanho — ela continua "existindo" para o Windows
        # (então clique/teclado funcionam normalmente), só não aparece na tela.
        win.moveTo(-32000, -32000)
        time.sleep(0.2)
        win.activate()
        time.sleep(0.4)
    except Exception:
        pass  # não é fatal — segue tentando colar mesmo assim

    try:
        # Cola a mensagem via clipboard (mais confiável que digitar char a
        # char, principalmente com acentos e texto longo).
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "a")  # seleciona texto antigo no campo, se houver
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.2)
    finally:
        # Sempre devolve o foco pro terminal, mesmo se algo acima falhar —
        # é o comportamento esperado pelo usuário em qualquer caso.
        _restore_foreground_window(terminal_handle)


def poll_response_once() -> Optional[str]:
    """Checa (sem bloquear) se a resposta já está pronta.
    Retorna o texto se sim, None se ainda não. Usado por um timer da TUI
    em vez de um loop bloqueante, para não travar a interface."""
    ensure_bridge_dir()
    if SIGNAL_FILE.exists():
        try:
            SIGNAL_FILE.unlink()
        except OSError:
            pass
        if RESPONSE_FILE.exists():
            return RESPONSE_FILE.read_text(encoding="utf-8")
        return ""
    return None


def clear_pending_signal() -> None:
    """Limpa sinais antigos antes de esperar uma resposta nova."""
    ensure_bridge_dir()
    if SIGNAL_FILE.exists():
        try:
            SIGNAL_FILE.unlink()
        except OSError:
            pass
