# Libera o vis e o js para o balanceador: o acesso passa a ser publico, mas so pelos enderecos api.onias.site e
# login.onias.site, porque a entrada direta pelos enderecos run.app fica fechada. Rode depois da migracao dos dados.
$ErrorActionPreference = 'Stop'
$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$project = 'jobsnow-prd'
$region = 'southamerica-east1'
foreach ($service in 'jobsnow-vis', 'jobsnow-js') {
	& $gcloud run services add-iam-policy-binding $service --project=$project --region=$region --member=allUsers --role=roles/run.invoker --quiet | Out-Null
	if ($LASTEXITCODE -ne 0) { throw "falhou ao liberar $service" }
	& $gcloud run services update $service --project=$project --region=$region --ingress=internal-and-cloud-load-balancing --quiet | Out-Null
	if ($LASTEXITCODE -ne 0) { throw "falhou ao restringir a entrada de $service" }
	Write-Host "$service liberado pelo balanceador"
}
