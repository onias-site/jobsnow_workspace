# Sandbox de testes manuais: uma cópia congelada do ambiente local (Elasticsearch, API vis, API js, leitor do bot de
# suporte e front end), em portas próprias, para o usuário testar enquanto o código do workspace muda.
#
#   ES 9201 (transporte 9301) | vis 18081 | js 18082 (login) | front 3100 | bot de suporte próprio (token em sandbox-config.json)
#
# Tudo fica em C:\jobsnow-sandbox. O código (classes + jars) e o front são copiados do workspace no momento do snapshot
# e não mudam depois disso; os dados vêm de um snapshot só dos índices js_*, jn_*, jb_* e vis_* do ES de desenvolvimento.
# Os processos são criados pelo WMI, fora da árvore da sessão do Claude, e continuam no ar depois que ela termina.
#
# Uso: sandbox.ps1 -Action start | stop | status | refresh-code | refresh-data
param(
	[ValidateSet('start', 'stop', 'status', 'refresh-code', 'refresh-data')]
	[string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'

$Root = 'C:\jobsnow-sandbox'
$Workspace = 'C:\eclipse-workspaces\ccp'
$Java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$Node = 'C:\Program Files\nodejs\node.exe'
$EsHome = 'C:\elasticsearch-7.4.0'
$EsJavaHome = 'C:\Program Files\Java\jdk-11.0.20'
$DevEs = 'http://localhost:9200'
$SandboxEs = 'http://localhost:9201'
$SnapshotRepoName = 'jobsnow_sandbox'
$SnapshotRepoPath = 'C:\jn\snapshots\jobsnow-sandbox'
$SnapshotName = 'sandbox'
$CopiedIndices = 'js_*,jn_*,jb_*,vis_*'
$FrontPort = 3100

$Apps = @(
	@{ Name = 'vis-api'; Module = 'vis_rest-api_spring_jobsnow_dependency-chooser'; Main = 'com.vis.rest.api.VisRestApiSpringStarter'; Port = 18081 },
	@{ Name = 'js-api'; Module = 'js_rest-api_spring_jobsnow_dependency-chooser'; Main = 'com.js.rest.api.JsRestApiSpringStarter'; Port = 18082 },
	@{ Name = 'bot'; Module = 'jb_instant-messenger-listener_jobsnow_dependency-chooser'; Main = 'com.jb.instant.messenger.reader.JbInstantMessengerReaderStarter'; Port = 0 }
)

$CodeDir = Join-Path $Root 'code'
$JarsDir = Join-Path $CodeDir 'jars'
$FrontDir = Join-Path $Root 'front'
$LogsDir = Join-Path $Root 'logs'
$ConfigFile = Join-Path $Root 'sandbox-config.json'
$DataMarker = Join-Path $Root 'data-copied.txt'
$CodeMarker = Join-Path $CodeDir 'snapshot.txt'

function Write-Step([string]$text) { Write-Host "==> $text" }

function Test-Port([int]$port) {
	$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
	return $null -ne $listening
}

function Wait-Port([int]$port, [int]$seconds) {
	$deadline = (Get-Date).AddSeconds($seconds)
	while ((Get-Date) -lt $deadline) {
		if (Test-Port $port) { return $true }
		Start-Sleep -Seconds 2
	}
	return $false
}

# Cria o processo pelo WMI: ele não herda o job da sessão que chamou o script, então sobrevive ao fim dela.
function Start-Detached([string]$cmdFile, [string]$workDir) {
	$startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
	$arguments = @{ CommandLine = "cmd.exe /c `"$cmdFile`""; CurrentDirectory = $workDir; ProcessStartupInformation = $startup }
	$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments $arguments
	if ($result.ReturnValue -ne 0) { throw "Falha ao criar o processo de $cmdFile (WMI devolveu $($result.ReturnValue))" }
}

# Só java, node e os cmd dos scripts run-*.cmd: um shell que apenas cite a pasta do sandbox não pode ser derrubado.
function Get-SandboxProcesses([string]$filter) {
	$all = Get-CimInstance Win32_Process -Filter "Name='java.exe' or Name='node.exe' or Name='cmd.exe'" |
		Where-Object { $_.CommandLine -and $_.CommandLine -like '*jobsnow-sandbox*' } |
		Where-Object { $_.Name -ne 'cmd.exe' -or $_.CommandLine -like '*jobsnow-sandbox\run-*' }
	if ($filter) { $all = $all | Where-Object { $_.CommandLine -like "*$filter*" } }
	return @($all)
}

function Stop-Tree([int]$processId) {
	& cmd.exe /c "taskkill /T /F /PID $processId >nul 2>&1"
	$global:LASTEXITCODE = 0
}

function Stop-Port([int]$port) {
	$connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
	foreach ($connection in $connections) { Stop-Tree $connection.OwningProcess }
}

# ---------------------------------------------------------------- configuração

function Get-SandboxConfig {
	if (-not (Test-Path $ConfigFile)) {
		New-Item -ItemType Directory -Force $Root | Out-Null
		$template = [ordered]@{ supportBotToken = '' } | ConvertTo-Json
		[IO.File]::WriteAllText($ConfigFile, $template, (New-Object Text.UTF8Encoding($false)))
	}
	$config = Get-Content $ConfigFile -Raw | ConvertFrom-Json
	return $config
}

# O application_properties do sandbox: o mesmo do desenvolvimento, com o ES 9201 e o bot de suporte do sandbox.
function Get-SandboxApplicationProperties([string]$botToken) {
	$devProperties = [Environment]::GetEnvironmentVariable('application_properties', 'Machine')
	if (-not $devProperties) { $devProperties = [Environment]::GetEnvironmentVariable('application_properties', 'User') }
	if (-not $devProperties) { throw 'Variavel de ambiente application_properties nao encontrada' }
	$properties = $devProperties | ConvertFrom-Json
	$properties.'elasticsearch.address' = $SandboxEs
	if ($botToken) { $properties.bots.support = $botToken }
	return ($properties | ConvertTo-Json -Compress -Depth 10)
}

# ---------------------------------------------------------------- snapshot do código

function Copy-Directory([string]$source, [string]$target, [string[]]$excludedDirs) {
	$arguments = @($source, $target, '/MIR', '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:1', '/W:1')
	if ($excludedDirs) { $arguments += '/XD'; $arguments += $excludedDirs }
	& robocopy.exe @arguments | Out-Null
	if ($LASTEXITCODE -ge 8) { throw "robocopy falhou ($LASTEXITCODE) copiando $source" }
	$global:LASTEXITCODE = 0
}

function New-CodeSnapshot {
	$m2Repository = Join-Path $env:USERPROFILE '.m2\repository'
	New-Item -ItemType Directory -Force $CodeDir, $JarsDir, $LogsDir | Out-Null
	foreach ($app in $Apps) {
		Write-Step "Snapshot do codigo: $($app.Name)"
		$moduleDir = Join-Path $Workspace $app.Module
		$appDir = Join-Path $CodeDir $app.Name
		$classpathFile = Join-Path $appDir 'maven-classpath.txt'
		New-Item -ItemType Directory -Force $appDir | Out-Null
		Push-Location $moduleDir
		try {
			& mvn.cmd -o -q compile dependency:build-classpath "-Dmdep.outputFile=$classpathFile"
			if ($LASTEXITCODE -ne 0) { throw "mvn falhou no modulo $($app.Module)" }
		} finally { Pop-Location }

		Copy-Directory (Join-Path $moduleDir 'target\classes') (Join-Path $appDir 'classes') $null

		# cada jar vai para code\jars no mesmo caminho relativo do .m2, e o classpath aponta para a cópia
		$entries = New-Object System.Collections.Generic.List[string]
		$entries.Add((Join-Path $appDir 'classes'))
		$mavenEntries = (Get-Content $classpathFile -Raw).Trim() -split ';'
		foreach ($entry in $mavenEntries) {
			if (-not $entry) { continue }
			$relative = if ($entry.StartsWith($m2Repository, [StringComparison]::OrdinalIgnoreCase)) { $entry.Substring($m2Repository.Length).TrimStart('\') } else { Join-Path 'external' (Split-Path $entry -Leaf) }
			$copy = Join-Path $JarsDir $relative
			if (Test-Path $entry -PathType Container) {
				Copy-Directory $entry $copy $null
			} else {
				New-Item -ItemType Directory -Force (Split-Path $copy -Parent) | Out-Null
				Copy-Item $entry $copy -Force
			}
			$entries.Add($copy)
		}
		# arquivo de argumentos do java: o classpath passa do limite de linha do cmd; barras normais porque a barra
		# invertida é caractere de escape nesse arquivo
		$classpath = ($entries | ForEach-Object { $_ -replace '\\', '/' }) -join ';'
		[IO.File]::WriteAllText((Join-Path $appDir 'java-args.txt'), "-cp $classpath", (New-Object Text.UTF8Encoding($false)))
	}
	$stamp = "Snapshot do codigo em $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
	[IO.File]::WriteAllText($CodeMarker, $stamp)
}

function New-FrontSnapshot {
	Write-Step 'Snapshot do front end'
	$source = Join-Path $Workspace 'jn_frontend_calistrato-react'
	New-Item -ItemType Directory -Force $FrontDir | Out-Null
	Copy-Directory $source $FrontDir @('node_modules', '.next', '.git')
	$nextCache = Join-Path $FrontDir '.next'
	if (Test-Path $nextCache) { Remove-Item -Recurse -Force $nextCache }
	# node_modules não é copiado (é enorme): a cópia usa o do workspace por junção
	$modules = Join-Path $FrontDir 'node_modules'
	if (-not (Test-Path $modules)) { & cmd.exe /c mklink /J "$modules" "$(Join-Path $source 'node_modules')" | Out-Null }
	# as URLs das APIs estão fixas no código do front: a cópia passa a apontar para as portas do sandbox
	$utf8 = New-Object Text.UTF8Encoding($false)
	$files = Get-ChildItem $FrontDir -Recurse -File -Include *.js, *.jsx, *.ts, *.tsx, *.mjs, *.cjs, *.json |
		Where-Object { $_.FullName -notlike "$modules\*" }
	foreach ($file in $files) {
		$text = [IO.File]::ReadAllText($file.FullName)
		if ($text -notmatch 'localhost:808[012]') { continue }
		$changed = $text -replace 'localhost:8080', 'localhost:18080' -replace 'localhost:8081', 'localhost:18081' -replace 'localhost:8082', 'localhost:18082'
		[IO.File]::WriteAllText($file.FullName, $changed, $utf8)
	}
}

# ---------------------------------------------------------------- scripts de execução

function Write-RunScripts([string]$applicationProperties) {
	New-Item -ItemType Directory -Force $LogsDir, (Join-Path $Root 'es\data'), (Join-Path $Root 'es\logs') | Out-Null
	$ascii = New-Object Text.UTF8Encoding($false)

	$es = @(
		'@echo off',
		"set `"JAVA_HOME=$EsJavaHome`"",
		"set `"ES_TMPDIR=$Root\es\tmp`"",
		"if not exist `"$Root\es\tmp`" mkdir `"$Root\es\tmp`"",
		"call `"$EsHome\bin\elasticsearch.bat`" -Ecluster.name=jobsnow-sandbox -Enode.name=jobsnow-sandbox -Ehttp.port=9201 -Etransport.port=9301 -Ediscovery.type=single-node -Epath.data=$Root\es\data -Epath.logs=$Root\es\logs > `"$LogsDir\es.log`" 2>&1"
	)
	[IO.File]::WriteAllText((Join-Path $Root 'run-es.cmd'), ($es -join "`r`n"), $ascii)

	foreach ($app in $Apps) {
		$appDir = Join-Path $CodeDir $app.Name
		$portArgument = if ($app.Port -gt 0) { "-Dserver.port=$($app.Port) " } else { '' }
		$lines = @(
			'@echo off',
			"set `"application_properties=$applicationProperties`"",
			"`"$Java`" -Dfile.encoding=UTF-8 $portArgument@`"$appDir\java-args.txt`" $($app.Main) > `"$LogsDir\$($app.Name).log`" 2>&1"
		)
		[IO.File]::WriteAllText((Join-Path $Root "run-$($app.Name).cmd"), ($lines -join "`r`n"), $ascii)
	}

	$front = @(
		'@echo off',
		"cd /d `"$FrontDir`"",
		"`"$Node`" `"$FrontDir\node_modules\next\dist\bin\next`" dev -p $FrontPort > `"$LogsDir\front.log`" 2>&1"
	)
	[IO.File]::WriteAllText((Join-Path $Root 'run-front.cmd'), ($front -join "`r`n"), $ascii)
}

# ---------------------------------------------------------------- dados

function Invoke-Es([string]$method, [string]$url, $body) {
	$parameters = @{ Method = $method; Uri = $url; ContentType = 'application/json'; TimeoutSec = 600 }
	if ($null -ne $body) { $parameters.Body = ($body | ConvertTo-Json -Depth 10 -Compress) }
	return Invoke-RestMethod @parameters
}

function Copy-Data {
	Write-Step "Copiando os indices $CopiedIndices do ES 9200 para o 9201 (snapshot e restore)"
	New-Item -ItemType Directory -Force $SnapshotRepoPath | Out-Null
	$repository = @{ type = 'fs'; settings = @{ location = $SnapshotRepoPath } }
	Invoke-Es 'PUT' "$DevEs/_snapshot/$SnapshotRepoName" $repository | Out-Null
	try { Invoke-Es 'DELETE' "$DevEs/_snapshot/$SnapshotRepoName/$SnapshotName" $null | Out-Null } catch { }
	$snapshot = @{ indices = $CopiedIndices; include_global_state = $false; ignore_unavailable = $true }
	Invoke-Es 'PUT' "$DevEs/_snapshot/$SnapshotRepoName/${SnapshotName}?wait_for_completion=true" $snapshot | Out-Null

	$readonlyRepository = @{ type = 'fs'; settings = @{ location = $SnapshotRepoPath; readonly = $true } }
	Invoke-Es 'PUT' "$SandboxEs/_snapshot/$SnapshotRepoName" $readonlyRepository | Out-Null
	Invoke-Es 'DELETE' "$SandboxEs/${CopiedIndices}?allow_no_indices=true&ignore_unavailable=true" $null | Out-Null
	$restore = @{ indices = $CopiedIndices; include_global_state = $false }
	Invoke-Es 'POST' "$SandboxEs/_snapshot/$SnapshotRepoName/$SnapshotName/_restore?wait_for_completion=true" $restore | Out-Null

	# o offset de leitura gravado é do bot de desenvolvimento; o bot do sandbox começa do zero
	$matchAll = @{ query = @{ match_all = @{} } }
	try { Invoke-Es 'POST' "$SandboxEs/jb_bot_update_id/_delete_by_query?refresh=true" $matchAll | Out-Null } catch { }

	$stamp = "Dados copiados do ES 9200 em $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
	[IO.File]::WriteAllText($DataMarker, $stamp)
}

# ---------------------------------------------------------------- ações

function Start-Es {
	if (Test-Port 9201) { return }
	Write-Step 'Subindo o Elasticsearch do sandbox (9201)'
	Start-Detached (Join-Path $Root 'run-es.cmd') $Root
	if (-not (Wait-Port 9201 180)) { throw "O ES do sandbox nao abriu a porta 9201; veja $LogsDir\es.log e $Root\es\logs" }
	$deadline = (Get-Date).AddSeconds(120)
	while ((Get-Date) -lt $deadline) {
		try {
			$health = Invoke-RestMethod "$SandboxEs/_cluster/health"
			if ($health.status -ne 'red') { return }
		} catch { }
		Start-Sleep -Seconds 2
	}
	throw 'O ES do sandbox nao ficou pronto'
}

function Start-Apps([bool]$hasBotToken) {
	foreach ($app in $Apps) {
		if ($app.Name -eq 'bot') {
			if (-not $hasBotToken) { Write-Step "Leitor do bot NAO subiu: falta supportBotToken em $ConfigFile"; continue }
			if ((Get-SandboxProcesses $app.Main).Count -gt 0) { continue }
		} elseif (Test-Port $app.Port) { continue }
		Write-Step "Subindo $($app.Name)"
		Start-Detached (Join-Path $Root "run-$($app.Name).cmd") $Root
	}
	if (-not (Test-Port $FrontPort)) {
		Write-Step "Subindo o front end ($FrontPort)"
		Start-Detached (Join-Path $Root 'run-front.cmd') $FrontDir
	}
	foreach ($app in $Apps) {
		if ($app.Port -gt 0 -and -not (Wait-Port $app.Port 120)) { Write-Step "ATENCAO: $($app.Name) nao abriu a porta $($app.Port); veja $LogsDir\$($app.Name).log" }
	}
	if (-not (Wait-Port $FrontPort 120)) { Write-Step "ATENCAO: o front nao abriu a porta $FrontPort; veja $LogsDir\front.log" }
}

function Stop-Apps {
	foreach ($app in $Apps) {
		if ($app.Port -gt 0) { Stop-Port $app.Port }
	}
	Stop-Port $FrontPort
	foreach ($process in (Get-SandboxProcesses $null)) {
		if ($process.CommandLine -like '*elasticsearch*' -or $process.CommandLine -like '*run-es.cmd*') { continue }
		Stop-Tree $process.ProcessId
	}
}

function Stop-All {
	Stop-Apps
	Stop-Port 9201
	foreach ($process in (Get-SandboxProcesses $null)) { Stop-Tree $process.ProcessId }
}

function Show-Status {
	$rows = @(
		@{ Name = 'Elasticsearch'; Up = (Test-Port 9201); Where = $SandboxEs },
		@{ Name = 'API vis'; Up = (Test-Port 18081); Where = 'http://localhost:18081' },
		@{ Name = 'API js (login)'; Up = (Test-Port 18082); Where = 'http://localhost:18082' },
		@{ Name = 'Leitor do bot'; Up = ((Get-SandboxProcesses 'JbInstantMessengerReaderStarter').Count -gt 0); Where = 'bot de suporte do sandbox' },
		@{ Name = 'Front end'; Up = (Test-Port $FrontPort); Where = "http://localhost:$FrontPort" }
	)
	foreach ($row in $rows) {
		$state = if ($row.Up) { 'no ar ' } else { 'parado' }
		Write-Host ("{0,-15} {1}  {2}" -f $row.Name, $state, $row.Where)
	}
	if (Test-Path $CodeMarker) { Write-Host (Get-Content $CodeMarker -Raw).Trim() }
	if (Test-Path $DataMarker) { Write-Host (Get-Content $DataMarker -Raw).Trim() }
}

function Start-Sandbox([bool]$refreshCode, [bool]$refreshData) {
	$config = Get-SandboxConfig
	$botToken = "$($config.supportBotToken)".Trim()
	$codeMissing = -not (Test-Path $CodeMarker)
	if ($refreshCode -or $codeMissing) {
		New-CodeSnapshot
		New-FrontSnapshot
	}
	$applicationProperties = Get-SandboxApplicationProperties $botToken
	Write-RunScripts $applicationProperties
	Start-Es
	$dataMissing = -not (Test-Path $DataMarker)
	if ($refreshData -or $dataMissing) { Copy-Data }
	Start-Apps ([bool]$botToken)
	Show-Status
}

switch ($Action) {
	'start' { Start-Sandbox $false $false }
	'stop' { Stop-All; Show-Status }
	'status' { Show-Status }
	'refresh-code' { Stop-Apps; Start-Sandbox $true $false }
	'refresh-data' { Stop-Apps; Start-Sandbox $false $true }
}
