import sys
import traceback
from pathlib import Path

# Registra tudo num arquivo de log
log = open("app_full_test.txt", "w", encoding="utf-8")

def L(msg):
    log.write(msg + "\n")
    log.flush()

L("=== Teste do LemoveCodeApp ===")
L("Python: " + sys.version)

try:
    L("1. Importando app...")
    from lemove_code.app import LemoveCodeApp
    L("2. Import OK")

    L("3. Criando instancia...")
    app = LemoveCodeApp(project_dir=Path("."))
    L("4. Instancia criada")

    L("5. Rodando em modo headless...")
    result = app.run(headless=True)
    L("6. Run retornou: " + str(result))

except Exception as e:
    L("EXCECAO: " + repr(e))
    L(traceback.format_exc())
finally:
    log.close()
