# Skill ccp-curriculos-para-uma-vaga: so producao, pelo tunel (com-tunel-de-producao.ps1).
#   -Etapa listar   le os curriculos ativos de producao para <Pasta>\curriculos-ativos.json (so leitura)
#   -Etapa simular  monta o e-mail de cada destinatario em <Pasta>\previa-<n>.html, sem enviar e sem gravar
#   -Etapa enviar   o mesmo, enviando pelo SendGrid de producao (nada e gravado em producao)
# A <Pasta> traz vaga.txt (texto da vaga), assunto.txt (assunto) e, para simular/enviar, linkedins.txt (um LinkedIn
# por linha, exatamente como em linkedinAddress). Nenhum valor de producao.json e impresso.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File curriculos-para-uma-vaga.ps1 -Etapa <etapa> -Pasta <pasta> [-Emails a,b]
param(
	[Parameter(Mandatory = $true)][ValidateSet('listar', 'simular', 'enviar')][string]$Etapa,
	[Parameter(Mandatory = $true)][string]$Pasta,
	[string[]]$Emails = @(),
	[string]$Front = 'https://onias.site',
	[string]$ApiVis = 'https://api.onias.site'
)
$ErrorActionPreference = 'Stop'
$scripts = $PSScriptRoot
$workspace = 'C:\eclipse-workspaces\ccp'
$tunnel = Join-Path $workspace 'documentation\deploy\com-tunel-de-producao.ps1'
$Pasta = (Resolve-Path $Pasta).Path

if ($Etapa -eq 'listar') {
	& $tunnel -Script (Join-Path $scripts 'listar-curriculos-ativos.py') -Argumentos (Join-Path $Pasta 'curriculos-ativos.json')
	exit 0
}

$Emails = @($Emails | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($Emails.Count -eq 0) { throw 'informe -Emails' }
foreach ($file in 'vaga.txt', 'assunto.txt', 'linkedins.txt') {
	if (-not (Test-Path (Join-Path $Pasta $file))) { throw "falta $file em $Pasta" }
}
& python -X utf8 -I (Join-Path $scripts 'montar-abertura.py') (Join-Path $Pasta 'vaga.txt') (Join-Path $Pasta 'abertura.html')
if ($LASTEXITCODE -ne 0) { throw 'falha ao montar a abertura' }

$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$data = Join-Path $Pasta 'dados-dos-curriculos.json'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
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
	$block = {
		$env:PYTHONIOENCODING = 'utf-8'
		& python -I (Join-Path $scripts 'ler-curriculos-escolhidos.py') (Join-Path $Pasta 'linkedins.txt') $data 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0 -or -not (Test-Path $data)) { "a leitura de producao falhou (saida $LASTEXITCODE)"; return }
		$env:application_properties = $productionProperties
		$ErrorActionPreference = 'Continue'
		& $java -Xmx2g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' (Join-Path $scripts 'SendJobResumes.java') $data $Front $ApiVis (Join-Path $Pasta 'abertura.html') (Join-Path $Pasta 'previa') $Etapa (Join-Path $Pasta 'assunto.txt') @Emails 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	& $tunnel -Bloco $block
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"executor saiu com $($state.exitCode)"
exit $state.exitCode
