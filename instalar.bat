@echo off
REM ============================================================
REM  Lemove Code — instalador (duplo clique)
REM  Chama install.ps1, que faz tudo: Python, Node, MCP, PATH.
REM  Para atualizar depois: lemovecode --update
REM ============================================================

setlocal
pushd "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set RESULT=%errorlevel%

popd
echo.
pause
exit /b %RESULT%
