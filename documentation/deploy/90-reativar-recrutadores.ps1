# Reativa em producao os recrutadores de uma lista de e-mails (pedido de 2026-11-17): cada um que estiver em
# vis_inactive_recruiter volta para vis_recruiter pelo delete da gemea (o mesmo caminho da visualizacao de curriculo,
# VisBusinessReactivateRecruiterWhoViewed), com os decorators. Feito para os 5 recrutadores que visualizaram curriculo
# durante o envio de 2026-11-17 (00:16 a 00:21) e foram inativados as 00:24 pelo defeito corrigido em vis_business aedd383.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre o tunel de producao e roda ReactivateRecruiters.java com a application_properties do ambiente trocando,
#      so neste processo, o Elasticsearch pelo do tunel. Nenhum segredo e nenhum e-mail sao impressos.
# A lista fica fora do repositorio (e-mails de recrutadores): um e-mail por linha.
# Sem -Gravar so mostra onde cada e-mail esta. Idempotente.
# Depois: o cache das entidades dura 1 hora.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 90-reativar-recrutadores.ps1 -Arquivo <lista> [-Gravar]
param([Parameter(Mandatory=$true)][string]$Arquivo, [switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\ReactivateRecruiters.java'
$list = (Resolve-Path $Arquivo).Path
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

	$executorArguments = @($list)
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
