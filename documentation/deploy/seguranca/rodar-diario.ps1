# Rodada diaria das suites de seguranca que nao precisam das APIs no ar (tarefa agendada \jobsnow\Seguranca diaria,
# 07:00, antes da cobertura das 10:00, que trava o target): 47 segredos, 48 dependencias, 49 postura do GCP (so leitura).
# Cada script grava o seu JSON em c:\logs\seguranca, lido pelo painel 51 (portal 37 > Backend > Seguranca).
# A varredura dinamica (50) e a SecuritySuite exigem as APIs locais no ar: rodam sob demanda.

$ErrorActionPreference = 'Continue'
$deploy = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:LOCALAPPDATA 'Python\bin\python.exe'
$logDir = 'c:\logs\seguranca'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ('rodada-' + (Get-Date -Format 'yyyy-MM-dd') + '.log')

foreach ($script in '47-seguranca-segredos.py', '48-seguranca-dependencias.py', '49-seguranca-postura-do-gcp.py') {
    "=== $script $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 $log
    # 2>&1 | Out-File: no PowerShell 5.1 o *>> grava em UTF-16 no meio do log UTF-8
    & $python -X utf8 (Join-Path $deploy $script) 2>&1 | ForEach-Object { "$_" } | Out-File -Append -Encoding utf8 $log
    "=== saida $LASTEXITCODE" | Out-File -Append -Encoding utf8 $log
}
