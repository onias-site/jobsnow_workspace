# Envia a um unico recrutador o e-mail de curriculos com TODOS os vis_resume de producao (SendProductionResumesToRecruiter.java).
# So producao (desde 2026-11-15): nada de Elasticsearch local nem de simulacao.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre UM tunel de producao e, dentro dele:
#      a. le producao, so leitura (ler-curriculos-de-producao.py), para um arquivo temporario;
#      b. roda o executor com a application_properties do ambiente trocando, so neste processo, o Elasticsearch pelo do
#         tunel (elasticsearch.address/secret) e tokenEmailKey, urlEmailKey e recruiterLinksSecret pelos de
#         C:\segredos\producao.json. Template, parametros de envio, marca de "ja enviado hoje" e a lista da tela
#         "Ver todos" (vis_recruiter_resumes) sao os de producao. Nenhum valor e impresso.
# O arquivo temporario e apagado no fim.
# Saidas: 0 ok; 2 nada a enviar; 3 SendGrid recusou (aviso em jn_jobsnow_warning de producao); 5 lista "Ver todos" nao conferiu.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File enviar-curriculos-de-producao-a-um-recrutador.ps1 -Email <recrutador>
param(
	[Parameter(Mandatory = $true)][string]$Email,
	[string]$Front = 'https://onias.site',
	[string]$ApiVis = 'https://api.onias.site'
)
$ErrorActionPreference = 'Stop'
$automation = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $automation '..\..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$data = Join-Path $env:TEMP ("curriculos-de-producao-" + [guid]::NewGuid().ToString('N') + ".json")
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $automation 'SendProductionResumesToRecruiter.java'
$reader = Join-Path $automation 'ler-curriculos-de-producao.py'
$localProperties = $env:application_properties
# o bloco roda dentro do com-tunel-de-producao.ps1, com o seu proprio escopo script: o resultado volta por esta
# hashtable, achada pelo escopo dinamico
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
		& python -I $reader $data 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0 -or -not (Test-Path $data)) { "a leitura de producao falhou (saida $LASTEXITCODE)"; return }
		$env:application_properties = $productionProperties
		$ErrorActionPreference = 'Continue'
		& $java -Xmx2g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor $Email $data $Front $ApiVis 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
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
