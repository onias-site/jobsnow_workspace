# Manda a outro endereco uma copia do e-mail de curriculos que um recrutador recebeu hoje (SendCopyOfRecruiterEmail.java):
# mesmos curriculos, mesma ordem, mesmos "voce nunca visualizou" e mesmo assunto, lidos do que o envio gravou em producao.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre UM tunel de producao e, dentro dele:
#      a. le producao, so leitura (ler-envio-de-hoje-de-um-recrutador.py), para um arquivo temporario;
#      b. roda o executor com a application_properties do ambiente trocando, so neste processo, o Elasticsearch pelo do
#         tunel e tokenEmailKey, urlEmailKey e recruiterLinksSecret pelos de C:\segredos\producao.json.
# Os links dos curriculos nao valem na copia (o token e o do recrutador original): nenhum clique grava visualizacao.
# Saidas: 0 ok; 2 nada a copiar; 3 SendGrid recusou (aviso em jn_jobsnow_warning de producao).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File enviar-copia-do-email-de-um-recrutador.ps1 -Recrutador <e-mail> -Destino <e-mail>
param(
	[Parameter(Mandatory = $true)][string]$Recrutador,
	[Parameter(Mandatory = $true)][string]$Destino,
	[string]$Front = 'https://onias.site',
	[string]$ApiVis = 'https://api.onias.site'
)
$ErrorActionPreference = 'Stop'
$automation = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $automation '..\..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$data = Join-Path $env:TEMP ("copia-do-email-" + [guid]::NewGuid().ToString('N') + ".json")
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $automation 'SendCopyOfRecruiterEmail.java'
$reader = Join-Path $automation 'ler-envio-de-hoje-de-um-recrutador.py'
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
	foreach ($key in 'tokenEmailKey', 'urlEmailKey', 'recruiterLinksSecret') {
		if (-not $production.$key) { throw "C:\segredos\producao.json nao tem $key" }
		$properties | Add-Member -NotePropertyName $key -NotePropertyValue $production.$key -Force
	}
	$productionSecret = $production.'elasticsearch.secret'
	if (-not $productionSecret) { $productionSecret = $production.elasticsearch.secret }
	if (-not $productionSecret) { throw 'C:\segredos\producao.json nao tem elasticsearch.secret' }
	$properties | Add-Member -NotePropertyName 'elasticsearch.address' -NotePropertyValue 'http://localhost:9210' -Force
	$properties | Add-Member -NotePropertyName 'elasticsearch.secret' -NotePropertyValue $productionSecret -Force
	$productionProperties = $properties | ConvertTo-Json -Depth 20 -Compress

	$sendInProduction = {
		$env:PYTHONIOENCODING = 'utf-8'
		& python -I $reader $Recrutador $data 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0 -or -not (Test-Path $data)) { "a leitura de producao falhou (saida $LASTEXITCODE)"; $state.exitCode = 2; return }
		$env:application_properties = $productionProperties
		$ErrorActionPreference = 'Continue'
		& $java -Xmx2g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor $Destino $data $Front $ApiVis 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	& (Join-Path $workspace 'documentation\deploy\com-tunel-de-producao.ps1') -Bloco $sendInProduction
} finally {
	$env:application_properties = $localProperties
	Pop-Location
	Remove-Item $data -ErrorAction SilentlyContinue
}
exit $state.exitCode
