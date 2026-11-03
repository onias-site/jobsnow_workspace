# Roda um script Python do deploy contra o ES de producao: abre o tunel IAP ate a VM (porta local 9210), le o
# Authorization de C:\segredos\producao.json para ES_DESTINO_AUTH (so neste processo) e fecha o tunel no fim.
# Uso: powershell -ExecutionPolicy Bypass -File com-tunel-de-producao.ps1 -Script <caminho do .py>
param([Parameter(Mandatory = $true)][string]$Script, [int]$Port = 9210)
$ErrorActionPreference = 'Stop'
$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$arguments = "compute ssh jobsnow-vm --project=jobsnow-prd --zone=southamerica-east1-a --tunnel-through-iap --quiet -- -L ${Port}:localhost:9200 -N"
$tunnel = Start-Process -FilePath $gcloud -ArgumentList $arguments -PassThru -WindowStyle Hidden
try {
	$open = $false
	for ($attempt = 0; $attempt -lt 45; $attempt++) {
		Start-Sleep -Seconds 2
		$client = New-Object Net.Sockets.TcpClient
		try { $client.Connect('127.0.0.1', $Port); $open = $true } catch { } finally { $client.Close() }
		if ($open) { break }
	}
	if (-not $open) { throw 'tunel nao abriu' }
	$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
	$auth = $production.'elasticsearch.secret'
	if (-not $auth) { $auth = $production.elasticsearch.secret }
	$env:ES_DESTINO_AUTH = $auth
	$env:PYTHONIOENCODING = 'utf-8'
	$ErrorActionPreference = 'Continue'
	& python -I $Script 2>&1 | ForEach-Object { "$_" }
	"script saiu com $LASTEXITCODE"
} finally {
	Remove-Item Env:ES_DESTINO_AUTH -ErrorAction SilentlyContinue
	if (-not $tunnel.HasExited) { & taskkill /T /F /PID $tunnel.Id *> $null }
}
