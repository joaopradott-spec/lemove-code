"""
lemove_code.cli
-----------------

Ponto de entrada do comando `lemovecode`. Depois de instalado
(`pip install -e .` dentro da pasta do projeto), digitar `lemovecode`
em qualquer cmd.exe/PowerShell abre a TUI estilo OpenCode.

Flags disponíveis:
  lemovecode                  Abre a TUI na pasta atual
  lemovecode <pasta>          Abre a TUI na pasta especificada
  lemovecode --update         Atualiza para a versão mais recente do GitHub
  lemovecode --version / -v   Mostra a versão instalada
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__

# URL do repositório — troque pelo seu quando publicar no GitHub
GITHUB_REPO = "https://github.com/SEU_USUARIO/lemove-code"
INSTALL_URL = f"git+{GITHUB_REPO}.git"


def _print_version() -> None:
    print(f"Lemove Code v{__version__}")


def _do_update() -> None:
    """Atualiza o pacote a partir do GitHub via pip."""
    print(f"\n  ⌬ Lemove Code — Atualizador")
    print(f"  Versão atual: v{__version__}")
    print(f"  Fonte: {GITHUB_REPO}\n")

    # Verifica se git está disponível (necessário para git+https://)
    git_ok = subprocess.run(
        ["git", "--version"],
        capture_output=True,
    ).returncode == 0

    if not git_ok:
        print("  [ERRO] Git não encontrado no PATH.")
        print("  Instale o Git em https://git-scm.com e tente novamente.\n")
        sys.exit(1)

    print("  Baixando a versão mais recente...\n")

    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", INSTALL_URL],
        text=True,
    )

    if result.returncode != 0:
        print("\n  [ERRO] A atualização falhou. Veja a mensagem acima.")
        print(f"  Você também pode atualizar manualmente:\n    pip install --upgrade {INSTALL_URL}\n")
        sys.exit(1)

    # Lê a versão nova após instalar
    try:
        # Recarrega o módulo para pegar a versão nova
        import importlib, lemove_code
        importlib.reload(lemove_code)
        new_version = lemove_code.__version__
    except Exception:
        new_version = "?"

    if new_version == __version__:
        print(f"\n  ✔ Já está na versão mais recente: v{__version__}\n")
    else:
        print(f"\n  ✔ Atualizado: v{__version__} → v{new_version}\n")
        print("  Abra um novo terminal para usar a versão atualizada.\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lemovecode",
        description="Lemove Code ⌬ — terminal estilo OpenCode usando o Claude Desktop como cérebro.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  lemovecode                  Abre na pasta atual\n"
            "  lemovecode ./meu-projeto    Abre em ./meu-projeto\n"
            "  lemovecode --update         Atualiza para a versão mais recente\n"
            "  lemovecode --version        Mostra a versão instalada\n"
        ),
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Pasta do projeto a abrir (padrão: pasta atual).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Atualiza o Lemove Code para a versão mais recente do GitHub.",
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Mostra a versão instalada e sai.",
    )

    args = parser.parse_args()

    if args.version:
        _print_version()
        return

    if args.update:
        _do_update()
        return

    # ── Abre a TUI ──────────────────────────────────────────────────
    target = args.directory or "."
    project_dir = Path(target).expanduser().resolve()

    if not project_dir.exists() or not project_dir.is_dir():
        print(f"Erro: a pasta '{project_dir}' não existe.", file=sys.stderr)
        sys.exit(1)

    from .app import run
    run(project_dir=project_dir)


if __name__ == "__main__":
    main()
