# Para, liga ou lista os consumidores das filas (PM2 do usuario jobsnow) na VM de producao, pelo SSH do IAP. Os scripts
# de reindexacao (82, 84, 91, 99) rodam com os consumidores parados: stop antes, start depois.
# O comando vai em base64 para as aspas e os pipes nao quebrarem entre o PowerShell, o cmd e o ssh.
# Uso: powershell -ExecutionPolicy Bypass -File pm2-na-vm.ps1 -Acao stop|start|ls
param(
	[Parameter(Mandatory = $true)][ValidateSet('stop', 'start', 'ls')][string]$Acao,
	[string]$Project = 'jobsnow-prd',
	[string]$Zone = 'southamerica-east1-a',
	[string]$VmName = 'jobsnow-vm'
)
$ErrorActionPreference = 'Stop'
$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$pm2 = 'env PM2_HOME=/home/jobsnow/.pm2 pm2'
$commands = @{
	'stop'  = "$pm2 stop all >/dev/null && $pm2 ls"
	'start' = "$pm2 start all >/dev/null && $pm2 ls"
	'ls'    = "$pm2 ls"
}
$bytes = [Text.Encoding]::UTF8.GetBytes($commands[$Acao])
$encoded = [Convert]::ToBase64String($bytes)
$remote = "echo $encoded | base64 -d | sudo -u jobsnow -H bash"
& cmd /c "`"$gcloud`" compute ssh $VmName --zone=$Zone --project=$Project --tunnel-through-iap --quiet --command=`"$remote`" 2>&1" | ForEach-Object { "$_" }
if ($LASTEXITCODE -ne 0) { throw "falhou: pm2 $Acao" }
