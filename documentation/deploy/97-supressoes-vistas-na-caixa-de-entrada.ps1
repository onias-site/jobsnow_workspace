# Grava em producao, em jn_email_suppressed (lista bounces), os enderecos que recusaram de vez o e-mail de curriculos mas
# que a carga diaria das supressoes nunca trouxe (2026-11-19): a recusa so chegou a caixa curriculos@onias.site (o servidor
# de destino aceitou do SendGrid e devolveu depois) ou o SendGrid a classificou como blocks, que nao suprime. Achados lendo
# o INBOX e o Spam do Thunderbird e cruzando com as listas do SendGrid: so recusas permanentes (destinatario ou dominio
# inexistente, 5.1.x, 5.3.3, 5.4.1 do Microsoft 365, 5.4.310, grupo do Google inexistente); caixa cheia, politica e loop
# de e-mail (5.4.14) ficam de fora.
# Grava pelo save da entidade (SaveEmailSuppressions.java), com os decorators: a primeira gravacao publica o evento e a vis
# inativa o recrutador (VisBusinessInactivateSuppressedRecruiter), como a carga diaria.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre o tunel de producao e roda o executor com a application_properties do ambiente trocando, so neste processo, o
#      Elasticsearch pelo do tunel. Nenhum segredo e nenhum e-mail sao impressos.
# A lista fica fora do repositorio (e-mails de recrutadores): TSV sem cabecalho email, created (segundos), status, reason.
# Sem -Gravar so mostra a situacao de cada linha. Idempotente.
# Depois: o cache das entidades dura 1 hora.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 97-supressoes-vistas-na-caixa-de-entrada.ps1 -Arquivo <lista.tsv> [-Gravar]
param([Parameter(Mandatory=$true)][string]$Arquivo, [switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\SaveEmailSuppressions.java'
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
