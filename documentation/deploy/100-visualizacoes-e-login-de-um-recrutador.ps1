# Apaga em producao as visualizacoes de curriculo e o login de um recrutador, sem rastro (2026-11-20, pedido para
# curriculos@onias.site, recrutador de teste do proprio usuario). O recrutador (vis_recruiter) fica.
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. com o tunel aberto: o Python lista o LinkedIn legivel de cada visualizacao (filhos do grupo
#      vis_viewed_resumes_of_the_recruiter); o DeleteViewsAndLoginOfARecruiter.java apaga pela entidade (deleteAnyWhere,
#      com os decorators que descontam os contadores do jn_grouper) as visualizacoes, o token, a senha, as respostas do
#      cadastro e o jn_login_email; o Python apaga os grupos de sessoes ja expurgadas (o historico de cada registro, um grupo do jn_grouper desde
#      2026-11-20, sai com o registro).
# Sem -Gravar so mostra o que existe. O e-mail vai por variavel de ambiente, nunca e impresso.
# Depois: o cache (Memorystore) das APIs guarda os registros lidos por ate 1 hora.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 100-visualizacoes-e-login-de-um-recrutador.ps1 -Email <e-mail> [-Gravar]
param([Parameter(Mandatory = $true)][string]$Email, [switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\DeleteViewsAndLoginOfARecruiter.java'
$helper = Join-Path $deploy '100-visualizacoes-e-login-de-um-recrutador.py'
$linkedins = Join-Path $env:TEMP 'visualizacoes-do-recrutador.txt'
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

	$executorArguments = @($Email, $linkedins)
	$cleanArguments = @('limpar')
	if ($Gravar) { $executorArguments += '--gravar'; $cleanArguments += '--gravar' }
	$deleteInProduction = {
		$env:RECRUTADOR_EMAIL = $Email
		$ErrorActionPreference = 'Continue'
		& python -I $helper 'listar' $linkedins 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { $state.exitCode = $LASTEXITCODE; return }
		$env:application_properties = $productionProperties
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
		if ($state.exitCode -ne 0) { return }
		& python -I $helper @cleanArguments 2>&1 | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
	}
	& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $deleteInProduction
} finally {
	$env:application_properties = $localProperties
	Remove-Item Env:RECRUTADOR_EMAIL -ErrorAction SilentlyContinue
	Remove-Item $linkedins -ErrorAction SilentlyContinue
	Pop-Location
}
"saiu com $($state.exitCode)"
exit $state.exitCode
