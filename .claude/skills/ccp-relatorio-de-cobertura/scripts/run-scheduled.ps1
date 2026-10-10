# Entrada da execução agendada (tarefa "\jobsnow\Relatorio de cobertura" do Agendador de Tarefas do Windows, todo dia
# às 12:00, pedida pelo usuário em 2026-10-10). Só roda a suíte quando o código mudou desde a última rodada completa
# (impressão digital de commit + alterações locais de cada módulo Maven, ver code-fingerprint.ps1). Quando roda, deixa
# no ar tudo o que a suíte precisa:
#   1. Elasticsearch local (localhost:9200): sobe o $ElasticHome\bin\elasticsearch.bat se estiver parado;
#   2. os jars do ~/.m2 iguais ao código (mvn install do agregador): os testes carregam os jars, e a cobertura compara
#      com eles; um módulo alterado e não instalado seria medido errado ou ficaria de fora;
#   3. as APIs jn (8080) e vis (8081), medidas: coverage-report.ps1 -RestartApis sobe as duas com o agente JaCoCo e,
#      se já havia uma rodando fora do Eclipse, a devolve sem agente no fim (uma API do Eclipse nunca é parada).
# Telegram, e-mail, cache e mensageria não precisam de nada no ar: nos testes são falsos ou locais.
# Grava um log por execução em <OutDir>\scheduled-logs. Não publica o Artifact: isso continua sendo feito pelo Claude.
param(
	[string]$Root = 'C:\eclipse-workspaces\ccp',
	[string]$OutDir = (Join-Path $env:TEMP 'ccp-coverage'),
	[string]$ElasticHome = 'C:\elasticsearch-7.4.0',
	# roda mesmo sem mudança no código (para testar a execução agendada à mão)
	[switch]$Force
)

$logDir = Join-Path $OutDir 'scheduled-logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("coverage-" + (Get-Date).ToString('yyyy-MM-dd_HHmm') + '.log')
function Write-Log([string]$text) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $text" | Out-File $log -Append -Encoding utf8 }

. (Join-Path $PSScriptRoot 'code-fingerprint.ps1')
$fingerprintFile = Join-Path (Split-Path $PSScriptRoot -Parent) 'history\last-code-fingerprint.txt'

# 1. o código mudou desde a última rodada completa?
$current = Get-CodeFingerprint -Root $Root
$previous = if (Test-Path $fingerprintFile) { [IO.File]::ReadAllText($fingerprintFile) } else { '' }
if (-not $Force -and $previous -and $previous.Trim() -eq $current.Trim()) {
	Write-Log 'Código sem mudança desde a última rodada completa: nada a fazer.'
	exit 0
}
$changed = if ($previous) { (Compare-CodeFingerprint $previous $current) -join ', ' } else { 'sem rodada anterior registrada' }
Write-Log "Código mudou ($changed). Preparando a rodada."

# 2. Elasticsearch
function Test-Elastic {
	try { return (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 'http://localhost:9200').StatusCode -eq 200 } catch { return $false }
}
if (-not (Test-Elastic)) {
	$bat = Join-Path $ElasticHome 'bin\elasticsearch.bat'
	if (-not (Test-Path $bat)) { Write-Log "Elasticsearch fora do ar e $bat não existe: rodada cancelada."; exit 1 }
	Write-Log "Elasticsearch fora do ar: subindo $bat"
	Start-Process -FilePath $bat -WorkingDirectory $ElasticHome -WindowStyle Hidden | Out-Null
	$deadline = (Get-Date).AddMinutes(4)
	while (-not (Test-Elastic)) {
		if ((Get-Date) -gt $deadline) { Write-Log 'Elasticsearch não respondeu em 4 minutos: rodada cancelada.'; exit 1 }
		Start-Sleep -Seconds 5
	}
	Write-Log 'Elasticsearch no ar (fica rodando depois da rodada).'
}

# 3. jars do ~/.m2 iguais ao código
Write-Log 'mvn -o install -DskipTests no agregador'
Push-Location $Root
$ErrorActionPreference = 'Continue'
$mvn = @(& mvn -o -q install -DskipTests 2>&1 | ForEach-Object { "$_" })
$mvnExit = $LASTEXITCODE
Pop-Location
if ($mvnExit -ne 0) {
	$mvn | Select-Object -Last 40 | Out-File $log -Append -Encoding utf8
	Write-Log 'mvn install falhou (com o Eclipse aberto, um lock em target/ costuma ser a causa): rodada cancelada; tenta de novo amanhã.'
	exit 1
}

# 4. suíte inteira com cobertura, APIs jn e vis medidas
Write-Log 'Rodando coverage-report.ps1 -RestartApis'
$exit = 0
try {
	& (Join-Path $PSScriptRoot 'coverage-report.ps1') -Root $Root -OutDir $OutDir -RestartApis *>&1 | ForEach-Object { "$_" } | Out-File $log -Append -Encoding utf8
} catch {
	# coverage-report.ps1 para com throw (ErrorActionPreference Stop): o motivo vai para o log
	Write-Log "coverage-report.ps1 falhou: $($_.Exception.Message)"
	$exit = 1
}
# a impressão digital só é gravada pelo coverage-report.ps1 quando a rodada chega ao histórico: uma rodada que falhou
# é tentada de novo no dia seguinte
Write-Log "Fim (código de saída $exit)."
exit $exit
