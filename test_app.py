import sys
import traceback
from pathlib import Path

try:
    from lemove_code.app import LemoveCodeApp

    # Testa só o compose/mount sem abrir janela
    app = LemoveCodeApp(project_dir=Path("."))
    result = app.run(headless=True)

    with open("app_test.txt", "w", encoding="utf-8") as f:
        f.write("App headless OK, result=" + str(result) + "\n")

except Exception as e:
    with open("app_test.txt", "w", encoding="utf-8") as f:
        f.write("ERRO:\n" + traceback.format_exc())
