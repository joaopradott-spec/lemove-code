@echo off
REM ============================================================
REM  Lemove Code — instalador
REM
REM  Instala o pacote em modo "editavel" (pip install -e .), o que
REM  cria o comando "lemovecode" no PATH do Python. Depois disso,
REM  digitar "lemovecode" em qualquer cmd.exe ou PowerShell abre a
REM  interface, de qualquer pasta do sistema.
REM
REM  Para atualizar depois: lemovecode --update
REM ============================================================

setlocal

echo.
echo   ⌬  Lemove Code — Instalador
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH. Instale o Python 3.9+ primeiro
    echo        ^(marque "Add python.exe to PATH" durante a instalacao^).
    pause
    exit /b 1
)

pushd "%~dp0"

python -m pip install --upgrade pip >nul
python -m pip install -e .
set INSTALL_RESULT=%errorlevel%

popd

if %INSTALL_RESULT% neq 0 (
    echo.
    echo [ERRO] A instalacao falhou. Veja a mensagem acima.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Instalado com sucesso!
echo.
echo   Abra um NOVO terminal e use:
echo.
echo     lemovecode             Abre a interface
echo     lemovecode --update    Atualiza para a versao mais recente
echo     lemovecode --version   Mostra a versao instalada
echo.
echo   Se o comando nao for reconhecido, adicione a pasta Scripts
echo   do Python ao PATH do Windows.
echo ============================================================
echo.
pause
