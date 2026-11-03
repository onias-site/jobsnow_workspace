# Item M do deploy: Memorystore for Valkey, com endpoint unico, sem autenticacao nem TLS, como GcpMemoryStore espera.
# O acesso fica restrito a rede privada jobsnow-vpc. A criacao leva alguns minutos. Pode rodar de novo.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$Instance = 'jobsnow-cache'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$networkPath = "projects/$Project/global/networks/$Network"
$subnetPath = "projects/$Project/regions/$Region/subnetworks/$Subnet"

& $gcloud network-connectivity service-connection-policies describe jobsnow-memorystore --region=$Region --project=$Project --format='value(name)' *> $null
if ($LASTEXITCODE -ne 0) {
	& $gcloud network-connectivity service-connection-policies create jobsnow-memorystore --network=$networkPath --region=$Region --project=$Project --service-class=gcp-memorystore --subnets=$subnetPath --quiet 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw 'falhou a politica de conexao' }
}

& $gcloud memorystore instances describe $Instance --location=$Region --project=$Project --format='value(name)' *> $null
if ($LASTEXITCODE -ne 0) {
	& $gcloud memorystore instances create $Instance --location=$Region --project=$Project --node-type=shared-core-nano --shard-count=1 --replica-count=0 --mode=cluster-disabled --transit-encryption-mode=transit-encryption-disabled --authorization-mode=auth-disabled "--psc-auto-connections=network=$networkPath,projectId=$Project" --quiet 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw 'falhou a instancia' }
}

& $gcloud memorystore instances describe $Instance --location=$Region --project=$Project --format='value(state,nodeType,engineVersion,endpoints[0].connections[0].pscAutoConnection.ipAddress,endpoints[0].connections[0].pscAutoConnection.port)' 2>&1 | ForEach-Object { "$_" }
