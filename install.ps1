# ============================================================
#  Lemove Code - Instalador (estilo opencode: 1 comando, pronto)
#
#  Uso:
#    powershell -ExecutionPolicy Bypass -File install.ps1
#  ou duplo clique em instalar.bat
#
#  Faz:
#    1. Checa Python 3.9+ e Node 18+
#    2. pip install -e .            (cria o comando "lemovecode")
#    3. npm install                  (deps do servidor MCP)
#    4. Registra o MCP no Claude Desktop (preserva config existente)
#    5. Cria ~/.lemove-code e verifica tudo
# ============================================================

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoDir

$failures = @()

function Step($msg) { Write-Host ""; Write-Host "== $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "   [OK] $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "   [AVISO] $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "   [ERRO] $msg" -ForegroundColor Red; $script:failures += $msg }

# ---------- 1. Pre-requisitos ----------
Step "1/5 Checando pre-requisitos"

try {
    $pyVer = (python --version 2>&1).ToString()
    $pyNum = [version]($pyVer -replace '[^0-9.]', '' -replace '\.$', '')
    if ($pyNum -lt [version]"3.9") { Fail "Python $pyNum encontrado, precisa de 3.9+. Baixe em https://www.python.org/downloads/"; }
    else { Ok "Python $pyNum" }
} catch { Fail "Python nao encontrado no PATH. Instale o Python 3.9+ marcando 'Add python.exe to PATH'. https://www.python.org/downloads/" }

$nodeOk = $false
try {
    $nodeVer = (node --version 2>&1).ToString().TrimStart("v")
    if ([version]$nodeVer -lt [version]"18.0.0") { Warn "Node $nodeVer encontrado, recomendado 18+. MCP pode falhar. https://nodejs.org/" }
    else { Ok "Node v$nodeVer"; $nodeOk = $true }
} catch { Warn "Node nao encontrado. O comando 'lemovecode' vai funcionar, mas o MCP (Claude lendo/escrevendo arquivos) nao. Instale em https://nodejs.org/ e rode de novo." }

# ---------- 2. Pacote Python ----------
Step "2/5 Instalando o comando 'lemovecode'"
try {
    python -m pip install --upgrade pip | Out-Null
    python -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "pip retornou $LASTEXITCODE" }
    Ok "pacote instalado (pip install -e .)"
} catch { Fail "pip install falhou: $_" }

# ---------- 3. Deps do MCP ----------
Step "3/5 Instalando dependencias do servidor MCP"
if ($nodeOk) {
    try {
        npm install --omit=dev
        if ($LASTEXITCODE -ne 0) { throw "npm retornou $LASTEXITCODE" }
        Ok "node_modules instalado"
    } catch { Fail "npm install falhou: $_" }
} else {
    Warn "pulado (sem Node). Rode o instalador de novo depois de instalar o Node."
}

# ---------- 4. Registrar MCP no Claude Desktop ----------
Step "4/5 Registrando MCP no Claude Desktop"
try {
    $serverJs = Join-Path $RepoDir "server.js"

    # O Claude Desktop pode ser a versao classica (%APPDATA%\Claude)
    # ou a da Microsoft Store (outro caminho). Registra em todas
    # as instalacoes encontradas.
    $configPaths = @((Join-Path $env:APPDATA "Claude\claude_desktop_config.json"))
    $storeBase = Join-Path $env:LOCALAPPDATA "Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
    if (Test-Path -LiteralPath $storeBase) {
        $configPaths += (Join-Path $storeBase "claude_desktop_config.json")
    }

    if (-not $nodeOk) {
        Warn "pulado (sem Node). Depois de instalar o Node, rode o instalador de novo."
    } else {
        $utf8NoBom = New-Object System.Text.UTF8Encoding $false
        foreach ($configPath in $configPaths) {
            $claudeDir = Split-Path -Parent $configPath
            if (-not (Test-Path -LiteralPath $claudeDir)) {
                New-Item -ItemType Directory -Path $claudeDir | Out-Null
            }
            $config = @{}
            if (Test-Path -LiteralPath $configPath) {
                try {
                    # Compativel com Windows PowerShell 5.1 (sem -AsHashtable):
                    # le como objeto e normaliza para hashtable.
                    $raw = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
                    foreach ($p in $raw.PSObject.Properties) { $config[$p.Name] = $p.Value }
                } catch {
                    $bak = "$configPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
                    Copy-Item -LiteralPath $configPath -Destination $bak -Force
                    Warn "config existente estava com JSON invalido, backup em $bak. Criando novo."
                    $config = @{}
                }
            }
            $servers = @{}
            if ($config.ContainsKey("mcpServers") -and $null -ne $config["mcpServers"]) {
                foreach ($p in $config["mcpServers"].PSObject.Properties) { $servers[$p.Name] = $p.Value }
            }
            # Se ja existe entrada criada pela UI ("Lemove_Code"), atualiza
            # o caminho dela em vez de duplicar o conector. Senao, cria
            # a canonica "lemove-code".
            $uiKey = @($servers.Keys) | Where-Object { $_ -ne "lemove-code" -and $_.Replace("_","-") -eq "lemove-code" } | Select-Object -First 1
            if ($uiKey) {
                $servers[$uiKey].args = @($serverJs)
                $servers[$uiKey].command = "node"
            } else {
                $servers["lemove-code"] = @{
                    command = "node"
                    args    = @($serverJs)
                }
            }
            $config["mcpServers"] = $servers
            # Sem BOM: alguns parsers de JSON rejeitam BOM no inicio do arquivo.
            [System.IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 10), $utf8NoBom)
            Ok "MCP registrado em $configPath"
        }
        Warn "feche e abra o Claude Desktop para ele carregar o MCP."
    }
} catch { Fail "registro do MCP falhou: $_" }

# ---------- 5. Bridge dir + verificacao ----------
Step "5/5 Verificando instalacao"
try {
    $bridgeDir = Join-Path $HOME ".lemove-code"
    if (-not (Test-Path -LiteralPath $bridgeDir)) { New-Item -ItemType Directory -Path $bridgeDir | Out-Null }
    Ok "pasta ~/.lemove-code pronta"

    $ver = (lemovecode --version 2>&1).ToString()
    Ok "comando na PATH: $ver"

    node --check (Join-Path $RepoDir "server.js")
    if ($LASTEXITCODE -ne 0) { throw "server.js com erro de sintaxe" }
    Ok "server.js valido"
} catch { Fail "verificacao falhou: $_" }

# ---------- Resumo ----------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
if ($failures.Count -eq 0) {
    Write-Host "  Instalado com sucesso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Proximos passos (1 min, so na primeira vez):"
    Write-Host "    1. Feche e abra o Claude Desktop (carregar o MCP)"
    Write-Host "    2. No Claude Desktop, em Settings > Profile > Personal"
    Write-Host "       preferences, cole isto:"
    Write-Host ""
    Write-Host "       Quando a mensagem terminar com [Lemocode], leia o bloco" -ForegroundColor Yellow
    Write-Host "       Lemove metadata, chame set_project com project e depois" -ForegroundColor Yellow
    Write-Host "       lemove_reply com text, request_id e session_id." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Uso:"
    Write-Host "    lemovecode               Abre no diretorio atual"
    Write-Host "    lemovecode <pasta>       Abre em outra pasta"
    Write-Host "    lemovecode --update      Atualiza do GitHub"
} else {
    Write-Host "  Instalacao concluiu com ERROS:" -ForegroundColor Red
    foreach ($f in $failures) { Write-Host "    - $f" -ForegroundColor Red }
}
Write-Host "============================================================"
Write-Host ""

if ($failures.Count -gt 0) { exit 1 }
