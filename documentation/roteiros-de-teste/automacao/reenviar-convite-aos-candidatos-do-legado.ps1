# Refaz o convite aos candidatos do indice legado profissionais2 (ReinviteLegacyCandidates.java), so com producao:
#   1. le os candidatos do Elasticsearch 7.4 do legado (porta 9201, ler-candidatos-do-legado.py) para um arquivo temporario;
#   2. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   3. abre o tunel de producao e roda o executor com a application_properties do ambiente trocando, so neste processo,
#      o Elasticsearch pelo do tunel e tokenEmailKey/urlEmailKey pelos de C:\segredos\producao.json. Curriculos, supressoes,
#      template e parametros de envio sao os de producao. Nenhum valor e impresso.
# Cada e-mail aceito grava o SHA-1 do destinatario no arquivo de controle: rodar de novo continua de onde parou.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File reenviar-convite-aos-candidatos-do-legado.ps1 [-Quantidade N]
#      -Quantidade 0 so conta (nada e enviado); sem -Quantidade envia a todos.
param(
	[int]$Quantidade = -1,
	[string]$Front = 'https://onias.site',
	[string]$Controle = 'c:\logs\convite-curriculos\reconvidados-2026-11-15.txt'
)
$ErrorActionPreference = 'Stop'
$automation = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $automation '..\..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$data = Join-Path $env:TEMP ("candidatos-do-legado-" + [guid]::NewGuid().ToString('N') + ".json")
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $automation 'ReinviteLegacyCandidates.java'
$localProperties = $env:application_properties
$state = @{ exitCode = 9 }
Push-Location $tests
try {
	$env:PYTHONIOENCODING = 'utf-8'
	& python -I (Join-Path $automation 'ler-candidatos-do-legado.py') $data
	if ($LASTEXITCODE -ne 0 -or -not (Test-Path $data)) { throw 'a leitura do legado falhou' }

	$ErrorActionPreference = 'Continue'
	& cmd /c "mvn -o -q test-compile dependency:build-classpath -Dmdep.outputFile=target\create-entities-cp.txt -Dmdep.includeScope=test"
	if ($LASTEXITCODE -ne 0) { throw 'falha na compilacao do Maven' }
	$ErrorActionPreference = 'Stop'
	$classpath = (Get-Content -Raw 'target\create-entities-cp.txt').Trim() -replace '\\', '/'
	Set-Content -Encoding ascii 'target\create-entities-args.txt' ('-cp "target/test-classes;target/classes;' + $classpath + '"')

	$properties = $localProperties | ConvertFrom-Json
	$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
	foreach ($key in 'tokenEmailKey', 'urlEmailKey') {
		if (-not $production.$key) { throw "C:\segredos\producao.json nao tem $key" }
		$properties | Add-Member -NotePropertyName $key -NotePropertyValue $production.$key -Force
	}
	$productionSecret = $production.'elasticsearch.secret'
	if (-not $productionSecret) { $productionSecret = $production.elasticsearch.secret }
	if (-not $productionSecret) { throw 'C:\segredos\producao.json nao tem elasticsearch.secret' }
	$properties | Add-Member -NotePropertyName 'elasticsearch.address' -NotePropertyValue 'http://localhost:9210' -Force
	$properties | Add-Member -NotePropertyName 'elasticsearch.secret' -NotePropertyValue $productionSecret -Force
	$productionProperties = $properties | ConvertTo-Json -Depth 20 -Compress

	# sem quantidade (-1), o java recebe so 3 argumentos e envia a todos
	$quantityArgument = if ($Quantidade -ge 0) { "$Quantidade" } else { $null }
	$sendInProduction = {
		$env:application_properties = $productionProperties
		$ErrorActionPreference = 'Continue'
		& $java -Xmx2g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor $data $Front $Controle $quantityArgument 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
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
