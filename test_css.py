import sys
import traceback
from pathlib import Path

log = open("css_test.txt", "w", encoding="utf-8")

def L(msg):
    log.write(msg + "\n")
    log.flush()

try:
    L("Testando CSS generation...")
    from lemove_code.app import _build_css, THEME_DARK, THEME_LIGHT
    css_dark = _build_css(THEME_DARK)
    L("CSS dark gerado, tamanho: " + str(len(css_dark)))
    css_light = _build_css(THEME_LIGHT)
    L("CSS light gerado, tamanho: " + str(len(css_light)))

    L("Testando _load_sessions...")
    from lemove_code.app import _load_sessions, _new_session
    sessions = _load_sessions()
    L("Sessions carregadas: " + str(len(sessions)))

    L("Testando _new_session...")
    s = _new_session(Path("."))
    L("Session criada: " + str(s["id"]))

    L("Testando bridge...")
    from lemove_code import bridge
    bridge.ensure_bridge_dir()
    L("Bridge dir OK")

    L("=== TUDO OK ===")

except Exception as e:
    L("ERRO: " + repr(e))
    L(traceback.format_exc())

log.close()
