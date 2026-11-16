# Corrige em producao os contadores do jn_grouper que contaram duas vezes o curriculo salvo duas vezes em 70 ms em
# 2026-11-15 23:47 (_id -749d8720e968a32759405b91b8468e6521e64cef, ddd 11): total de vis_resume, mes 202611, dia
# 20261115, ddd 11, tipo de curriculo e empresas proibidas ficaram com 1 a mais. A corrida que causou isso foi corrigida
# em 2026-11-16 (CcpMensageriaRecordLocks, ccp_commons_jobsnow).
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre o tunel de producao e roda SubtractAResumeCountedTwice.java com a application_properties do ambiente
#      trocando, so neste processo, o Elasticsearch pelo do tunel. Nenhum segredo e impresso.
# Sem -Gravar so mostra os contadores e o que mudaria. Com -Gravar so grava se o total atual de vis_resume for 68 (rodar
# de novo nao desconta outra vez).
# Depois: os contadores sao lidos com cache de 1 hora (APIs e front, que guarda os totais por 1 hora no navegador).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 88-curriculo-contado-duas-vezes.ps1 [-Gravar]
param([switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\SubtractAResumeCountedTwice.java'
$resumeId = '-749d8720e968a32759405b91b8468e6521e64cef'
$expectedTotal = '68'
$localProperties = $env:application_properties
$state = @{ exitCode = 9 }
Push-Location $tests
try {
	$ErrorActionPreference = 'Continue'
	& cmd /c "mvn -o -q test-compile dependency:build-classpath -Dmdep.outputFile=target\create-entities-cp.txt -Dmdep.includeScope=test"
	if ($LASTEXITCODE -ne 0) { throw 'falha na compilacao do Maven' }
	$ErrorActionPreference = 'Stop'
	$classpath = (Get-Content -Raw 'target\create-entities-cp.txt').Trim() -replace '\\', '/'
	Set-Content -Encoding ascii 'target\create-entities-args.txt' ('-cp "target/test-classes;target/classes;' + $classpath + '"')

	$properties = $localProperties | ConvertFrom-Json
	$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
	$productionSecret = $production.'elasticsearch.secret'
	if (-not $productionSecret) { $productionSecret = $production.elasticsearch.secret }
	if (-not $productionSecret) { throw 'C:\segredos\producao.json nao tem elasticsearch.secret' }
	$properties | Add-Member -NotePropertyName 'elasticsearch.address' -NotePropertyValue 'http://localhost:9210' -Force
	$properties | Add-Member -NotePropertyName 'elasticsearch.secret' -NotePropertyValue $productionSecret -Force
	$productionProperties = $properties | ConvertTo-Json -Depth 20 -Compress

	$executorArguments = @($resumeId, $expectedTotal)
	if ($Gravar) { $executorArguments += '--gravar' }
	$correctInProduction = {
		$env:application_properties = $productionProperties
		$ErrorActionPreference = 'Continue'
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $correctInProduction
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"executor saiu com $($state.exitCode)"
exit $state.exitCode
