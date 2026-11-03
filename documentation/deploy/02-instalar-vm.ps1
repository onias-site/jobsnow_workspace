# Gera a senha do Elasticsearch, guarda no Secret Manager e roda 02-instalar-vm.sh na VM pelo tunel do IAP.
# Nenhum valor secreto vai para a tela nem para a linha de comando.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Zone = 'southamerica-east1-a',
	[string]$VmName = 'jobsnow-vm',
	[string]$SecretName = 'jobsnow-elasticsearch-password'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$passwordFile = Join-Path $env:TEMP ("es-" + [guid]::NewGuid().ToString('N') + '.txt')
$utf8 = New-Object Text.UTF8Encoding($false)

try {
	$bytes = New-Object byte[] 32
	[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
	$password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
	[IO.File]::WriteAllText($passwordFile, $password, $utf8)

	& $gcloud secrets describe $SecretName --project $Project --format='value(name)' *> $null
	if ($LASTEXITCODE -ne 0) {
		& $gcloud secrets create $SecretName --project $Project --replication-policy=user-managed --locations=southamerica-east1 --data-file=$passwordFile --quiet 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { throw 'falhou ao criar o segredo' }
	} else {
		& $gcloud secrets versions access latest --secret=$SecretName --project $Project --out-file=$passwordFile --quiet 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { throw 'falhou ao ler o segredo' }
	}

	$sshArgs = @("--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet')
	$remotePassword = "/tmp/es-bootstrap-$([guid]::NewGuid().ToString('N'))"
	& $gcloud compute scp @sshArgs (Join-Path $PSScriptRoot '02-instalar-vm.sh') "${VmName}:/tmp/02-instalar-vm.sh" 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw 'falhou ao copiar o script' }
	& $gcloud compute scp @sshArgs $passwordFile "${VmName}:$remotePassword" *> $null
	if ($LASTEXITCODE -ne 0) { throw 'falhou ao copiar a senha' }
	& $gcloud compute ssh $VmName @sshArgs --command="sudo bash /tmp/02-instalar-vm.sh $remotePassword" 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw 'falhou ao instalar' }
} finally {
	if (Test-Path $passwordFile) { Remove-Item $passwordFile -Force -Confirm:$false }
}
