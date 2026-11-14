# Compila o que cada alvo pede, na ordem dos pom.xml, e publica: front, vis e js no Cloud Run por
# documentation\deploy\08-publicar-cloud-run.ps1; consumidores na VM por documentation\deploy\07-publicar-na-vm.ps1 -SoConsumidores;
# cron (o processo diario, Cloud Run Job jobsnow-processo-diario) por documentation\deploy\32-processo-diario-no-cloud-run.ps1.
# Uso: deploy.ps1 front | vis | js | consumidores | cron | todos (aceita mais de um). Com -SoListar so mostra a ordem de build, sem compilar nem publicar.
param(
	[Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
	[string[]]$Alvos,
	[switch]$SoListar
)

$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$modules = @{
	vis = 'vis_rest-api_spring_jobsnow_dependency-chooser'
	js = 'js_rest-api_spring_jobsnow_dependency-chooser'
	consumidores = 'ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser'
	cron = 'ccp_cron-tasks_jobsnow'
}

$requested = @($Alvos | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.ToLower() })
if ($requested -contains 'todos') { $requested = @('vis', 'js', 'front', 'consumidores', 'cron') }
foreach ($target in $requested) {
	if ($target -notin 'front', 'vis', 'js', 'consumidores', 'cron') { throw "alvo desconhecido: $target (use front, vis, js, consumidores, cron ou todos)" }
}
$requested = @($requested | Select-Object -Unique)
$mavenTargets = @($requested | Where-Object { $_ -ne 'front' })
$cloudRunTargets = @($requested | Where-Object { $_ -in 'front', 'vis', 'js' })

Set-Location $workspace
if ($mavenTargets.Count -gt 0) {
	$projectList = ($mavenTargets | ForEach-Object { $modules[$_] }) -join ','
	$log = Join-Path $env:TEMP 'ccp-deploy-maven.log'
	if ($SoListar) {
		& cmd /c "mvn -o -pl $projectList -am validate > `"$log`" 2>&1"
		$inOrder = $false
		foreach ($line in Get-Content $log) {
			if ($line -match 'Reactor Build Order') { $inOrder = $true; continue }
			if ($inOrder -and $line -match '^\[INFO\]\s*$') { continue }
			if ($inOrder -and $line -match '^\[INFO\] (\S.*?)\s+\[') { $Matches[1]; continue }
			if ($inOrder -and $line -match '^\[INFO\] -{3,}') { break }
		}
		if ($LASTEXITCODE -ne 0) { Get-Content $log -Tail 10 }
		exit $LASTEXITCODE
	}
	Write-Host "== build de $projectList e dependencias"
	$started = Get-Date
	& cmd /c "mvn -pl $projectList -am clean install -DskipTests > `"$log`" 2>&1"
	if ($LASTEXITCODE -ne 0) {
		Get-Content $log -Tail 25
		throw "build falhou; log em $log"
	}
	Write-Host "build concluido em $([int]((Get-Date) - $started).TotalSeconds) s"
}
if ($SoListar) { 'front nao usa Maven'; exit 0 }

if ($cloudRunTargets.Count -gt 0) {
	& (Join-Path $workspace 'documentation\deploy\08-publicar-cloud-run.ps1') -Servicos $cloudRunTargets -ManterSegredo
	if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($requested -contains 'consumidores') {
	# so o jar dos consumidores (e os arquivos de configuracao da VM); o cron.jar da VM fica como esta
	Write-Host "== consumidores na VM"
	& (Join-Path $workspace 'documentation\deploy\07-publicar-na-vm.ps1') -SoConsumidores
	if (-not $?) { exit 1 }
	Write-Host "consumidores publicados"
}
if ($requested -contains 'cron') {
	# nova imagem do job do processo diario; o agendamento fica pausado ou ligado como ja estiver
	Write-Host "== processo diario (Cloud Run Job)"
	& (Join-Path $workspace 'documentation\deploy\32-processo-diario-no-cloud-run.ps1')
	if (-not $?) { exit 1 }
	Write-Host "processo diario publicado"
	# o mesmo jar no job do reenvio diario do token de login (8h); o agendamento fica como ja estiver
	Write-Host "== reenvio do token de login (Cloud Run Job)"
	& (Join-Path $workspace 'documentation\deploy\54-reenvio-do-token-de-login-no-cloud-run.ps1')
	if (-not $?) { exit 1 }
	Write-Host "reenvio do token de login publicado"
}
exit 0
