# Compila o que cada servico pede, na ordem dos pom.xml, e publica no Cloud Run por documentation\deploy\08-publicar-cloud-run.ps1.
# Uso: deploy.ps1 front | vis | js | todos (aceita mais de um). Com -SoListar so mostra a ordem de build, sem compilar nem publicar.
param(
	[Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
	[string[]]$Alvos,
	[switch]$SoListar
)

$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$modules = @{
	vis = 'vis_rest-api_spring_jobsnow_dependency-chooser'
	js = 'js_rest-api_spring_jobsnow_dependency-chooser'
}

$requested = @($Alvos | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.ToLower() })
if ($requested -contains 'todos') { $requested = @('vis', 'js', 'front') }
foreach ($target in $requested) {
	if ($target -notin 'front', 'vis', 'js') { throw "alvo desconhecido: $target (use front, vis, js ou todos)" }
}
$requested = @($requested | Select-Object -Unique)
$apis = @($requested | Where-Object { $_ -ne 'front' })

Set-Location $workspace
if ($apis.Count -gt 0) {
	$projectList = ($apis | ForEach-Object { $modules[$_] }) -join ','
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

& (Join-Path $workspace 'documentation\deploy\08-publicar-cloud-run.ps1') -Servicos $requested -ManterSegredo
exit $LASTEXITCODE
