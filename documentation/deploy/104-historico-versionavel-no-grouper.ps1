# Leva para o jn_grouper o historico das entidades versionaveis de producao e apaga o indice jn_versionable (2026-11-20).
# Desde entao cada registro versionavel guarda suas versoes num grupo do jn_grouper (parentName
# jn_virtual_versionable_history, childName = entidade, parentJson = {entity, id, primaryKey}), lido pelo dono em
# GET /versionable-history/{email}/{entity}/{id} da js. Roda DEPOIS do deploy de js, vis, consumidores e cron, que ja
# gravam o historico nos grupos.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. com o tunel aberto, conforme a etapa:
#      contar   - MoveVersionableHistoryToGrouper.java sem argumento: conta linhas, registros e entidades;
#      gravar   - MoveVersionableHistoryToGrouper.java --gravar: grava os grupos (idempotente, junta com as versoes que
#                 ja estiverem no grupo, sem repetir);
#      conferir - MoveVersionableHistoryToGrouper.java --conferir: sai com 1 se faltar um grupo ou uma versao;
#      apagar   - o --conferir e, se saiu com 0, o 104-...py --apagar: apaga o jn_versionable quando ha snapshot
#                 SUCCESS das ultimas 36 horas que o contem (sem snapshot nada e apagado).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 104-historico-versionavel-no-grouper.ps1 -Etapa <contar|gravar|conferir|apagar>
param([Parameter(Mandatory = $true)][ValidateSet('contar', 'gravar', 'conferir', 'apagar')][string]$Etapa)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\MoveVersionableHistoryToGrouper.java'
$helper = Join-Path $deploy '104-historico-versionavel-no-grouper.py'
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

	$executorArguments = @()
	if ($Etapa -eq 'gravar') { $executorArguments = @('--gravar') }
	if ($Etapa -eq 'conferir' -or $Etapa -eq 'apagar') { $executorArguments = @('--conferir') }
	$runInProduction = {
		$ErrorActionPreference = 'Continue'
		$env:application_properties = $productionProperties
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
		if ($state.exitCode -ne 0 -or $Etapa -ne 'apagar') { return }
		& python -I $helper '--apagar' 2>&1 | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
	}
	& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $runInProduction
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"saiu com $($state.exitCode)"
exit $state.exitCode
