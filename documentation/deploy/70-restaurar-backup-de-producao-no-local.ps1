# Tarefa diaria desta maquina: baixa o backup do ES de producao (snapshot nativo no bucket gs://jobsnow-backup) e restaura
# o snapshot mais recente no ES 9.5.5 local (127.0.0.1:9200), sobrescrevendo os indices locais que estao no snapshot.
# Indices locais que nao estao no snapshot (entidades ainda nao levadas a producao) ficam como estao. O legado fica no 7.4.
# Uso: powershell -File 70-restaurar-backup-de-producao-no-local.ps1          (roda agora)
#      powershell -File 70-restaurar-backup-de-producao-no-local.ps1 -Agendar (cria a tarefa \jobsnow\Backup de producao no local)
param([switch]$Agendar, [string]$Horario = '05:30')

$ErrorActionPreference = 'Stop'
$taskName = 'Backup de producao no local'

if ($Agendar) {
	$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`""
	$trigger = New-ScheduledTaskTrigger -Daily -At $Horario
	$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)
	Register-ScheduledTask -TaskPath '\jobsnow\' -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
	Write-Output "tarefa \jobsnow\$taskName agendada todo dia as $Horario"
	return
}

$es = 'http://127.0.0.1:9200'
$bucket = 'gs://jobsnow-backup'
$repository = 'producao'
$folder = 'C:\elasticsearch-9.5.5\snapshots\producao'
$logFolder = 'C:\logs\backup-producao'
New-Item -ItemType Directory -Force $logFolder | Out-Null
$log = Join-Path $logFolder ((Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')

function Write-Log([string]$text) {
	$line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $text
	Add-Content -Path $log -Value $line -Encoding utf8
	Write-Output $line
}

function Invoke-Es([string]$method, [string]$path, $body = $null, [int]$timeout = 120) {
	$parameters = @{ Method = $method; Uri = $es + $path; ContentType = 'application/json'; TimeoutSec = $timeout }
	if ($null -ne $body) { $parameters.Body = ($body | ConvertTo-Json -Depth 10) }
	return Invoke-RestMethod @parameters
}

try {
	# depois de um boot o ES costuma estar desligado (sobe a mao no terminal): espera ate 2 h, conferindo a cada minuto
	$deadline = (Get-Date).AddHours(2)
	$cluster = $null
	while ($null -eq $cluster) {
		try { $cluster = Invoke-Es 'GET' '/' $null 10 } catch {
			if ((Get-Date) -gt $deadline) { throw "o ES em $es nao respondeu em 2 h" }
			if (-not $waitLogged) { Write-Log "ES em $es desligado; esperando ate $($deadline.ToString('HH:mm'))"; $waitLogged = $true }
			Start-Sleep -Seconds 60
		}
	}
	if ($cluster.cluster_name -ne 'jobsnow-es9') { throw "o ES em $es nao e o local (cluster $($cluster.cluster_name))" }

	$gcloud = (Get-Command gcloud.cmd -ErrorAction SilentlyContinue).Source
	if (-not $gcloud) { $gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' }
	New-Item -ItemType Directory -Force $folder | Out-Null
	Write-Log "baixando $bucket para $folder"
	# o gcloud escreve o progresso no stderr, que o PowerShell 5.1 trataria como erro com Stop
	$ErrorActionPreference = 'Continue'
	& $gcloud storage rsync $bucket $folder --recursive --delete-unmatched-destination-objects --quiet 2>&1 | ForEach-Object { Add-Content -Path $log -Value "$_" -Encoding utf8 }
	$ErrorActionPreference = 'Stop'
	if ($LASTEXITCODE -ne 0) { throw "gcloud storage rsync terminou com codigo $LASTEXITCODE" }

	# registra de novo a cada execucao: o ES guarda em memoria a geracao do repositorio, que muda com os arquivos baixados
	try { Invoke-Es 'DELETE' "/_snapshot/$repository" | Out-Null } catch {}
	Invoke-Es 'PUT' "/_snapshot/$repository" @{ type = 'fs'; settings = @{ location = $folder; readonly = $true } } | Out-Null

	$snapshots = (Invoke-Es 'GET' "/_snapshot/$repository/_all").snapshots | Where-Object { $_.state -eq 'SUCCESS' }
	if (-not $snapshots) { throw 'nenhum snapshot com sucesso no backup' }
	$latest = $snapshots | Sort-Object { [long]$_.end_time_in_millis } | Select-Object -Last 1
	$indices = @($latest.indices | Where-Object { $_ -match '^(jn|js|vis|jb)_' } | Sort-Object)
	Write-Log "snapshot $($latest.snapshot) de $($latest.end_time), versao $($latest.version), $($indices.Count) indices"

	$local = @((Invoke-Es 'GET' '/_cat/indices?h=index&format=json') | ForEach-Object { $_.index })
	$toDelete = @($indices | Where-Object { $local -contains $_ })
	if ($toDelete.Count -gt 0) {
		Write-Log "apagando $($toDelete.Count) indices locais que serao sobrescritos"
		Invoke-Es 'DELETE' ('/' + ($toDelete -join ',')) | Out-Null
	}

	$restoreBody = @{ indices = ($indices -join ','); include_global_state = $false; include_aliases = $true; index_settings = @{ 'index.number_of_replicas' = 0 } }
	$restore = Invoke-Es 'POST' "/_snapshot/$repository/$($latest.snapshot)/_restore?wait_for_completion=true" $restoreBody 3600
	$shards = $restore.snapshot.shards
	Write-Log "restaurados $($restore.snapshot.indices.Count) indices, shards: total $($shards.total), sucesso $($shards.successful), falha $($shards.failed)"
	if ($shards.failed -gt 0) { throw 'restauracao com shards falhos' }

	$total = 0
	foreach ($index in $indices) { $total += (Invoke-Es 'GET' "/$index/_count").count }
	Write-Log "concluido: $total documentos nos indices restaurados; reinicie as APIs locais (cache em memoria)"
} catch {
	Write-Log ('ERRO: ' + $_.Exception.Message)
	exit 1
}
