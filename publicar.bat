@echo off
setlocal EnableExtensions
pushd "%~dp0"

echo ============================================================
echo   Lemove Code - Publicador GitHub
echo ============================================================
echo.

where git >nul 2>&1 || goto :no_git
where node >nul 2>&1 || goto :no_node
where python >nul 2>&1 || goto :no_python

set "VERSION=%~1"
if not defined VERSION set "VERSION=1.0.0"
if /i not "%VERSION:~0,1%"=="v" set "VERSION=v%VERSION%"

powershell -NoProfile -Command "if ('%VERSION%' -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$') { exit 1 }"
if errorlevel 1 (
  echo [ERRO] Versao invalida: %VERSION%
  echo Use: publicar.bat 1.0.0
  goto :fail
)

for /f "delims=" %%B in ('git branch --show-current') do set "BRANCH=%%B"
if not defined BRANCH (
  echo [ERRO] HEAD destacado. Troque para uma branch antes de publicar.
  goto :fail
)

echo Versao: %VERSION%
echo Branch: %BRANCH%
echo.
echo [1/6] Verificando alteracoes...
git diff --check || goto :fail
git status --short
echo.
set /p "CONFIRM=Publicar exatamente os arquivos listados acima? Digite SIM: "
if /i not "%CONFIRM%"=="SIM" goto :cancel

echo.
echo [2/6] Executando testes Python...
python -m pytest -q || goto :fail

echo.
echo [3/6] Executando testes Node e MCP...
call npm test || goto :fail
node test-client.js || goto :fail
node --check server.js || goto :fail

echo.
echo [4/6] Sincronizando com origin...
git fetch origin || goto :fail
git merge-base --is-ancestor "origin/%BRANCH%" HEAD
if errorlevel 1 (
  echo [ERRO] origin/%BRANCH% possui commits que nao estao no seu HEAD.
  echo Rode git pull --rebase e revise o resultado antes de publicar.
  goto :fail
)

git rev-parse -q --verify "refs/tags/%VERSION%" >nul 2>&1
if not errorlevel 1 (
  echo [ERRO] A tag local %VERSION% ja existe.
  goto :fail
)
git ls-remote --exit-code --tags origin "refs/tags/%VERSION%" >nul 2>&1
if not errorlevel 1 (
  echo [ERRO] A tag %VERSION% ja existe no GitHub.
  goto :fail
)

echo.
echo [5/6] Criando commit e tag...
git add -A || goto :fail
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Release %VERSION%" || goto :fail
) else (
  echo Nenhuma alteracao nova para commit; usando o HEAD atual.
)
git tag -a "%VERSION%" -m "Lemove Code %VERSION%" || goto :fail

echo.
echo [6/6] Enviando branch e tag atomicamente...
git push --atomic origin "%BRANCH%" "%VERSION%" || goto :push_fail

echo.
echo [OK] %VERSION% publicada no GitHub.
echo A tag acionou o workflow de Release. Acompanhe em:
echo https://github.com/joaopradott-spec/lemove-code/actions
popd
exit /b 0

:push_fail
echo [ERRO] O push falhou. Nada foi enviado parcialmente pelo push atomico.
echo A tag local %VERSION% ficou criada; revise antes de tentar novamente.
goto :fail

:no_git
echo [ERRO] Git nao encontrado no PATH.
goto :fail
:no_node
echo [ERRO] Node nao encontrado no PATH.
goto :fail
:no_python
echo [ERRO] Python nao encontrado no PATH.
goto :fail
:cancel
echo Publicacao cancelada. Nenhum commit, tag ou push foi feito.
popd
exit /b 2
:fail
echo.
echo Publicacao interrompida.
popd
exit /b 1
