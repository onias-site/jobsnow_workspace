# Item I do deploy: balanceador global no IP fixo. onias.site e www vao ao front, api a vis e login a js.
# Pode rodar de novo: pula o que ja existe. O certificado so fica ativo depois que os quatro nomes apontarem para o IP.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$AddressName = 'jobsnow-ip',
	[string]$Domain = 'onias.site'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$projectArg = "--project=$Project"

function Run([string]$label, [string[]]$arguments) {
	Write-Host "== $label"
	& $gcloud @arguments 2>&1 | ForEach-Object { "$_" } | Select-Object -Last 3 | ForEach-Object { Write-Host $_ }
	if ($LASTEXITCODE -ne 0) { throw "falhou: $label" }
}

function Ensure([string]$label, [string[]]$describe, [string[]]$create) {
	& $gcloud @describe $projectArg *> $null
	if ($LASTEXITCODE -eq 0) { Write-Host "ja existe: $label"; return }
	Run $label ($create + $projectArg + '--quiet')
}

foreach ($service in 'front', 'vis', 'js') {
	$neg = "jobsnow-$service-neg"
	$backend = "jobsnow-$service-backend"
	Ensure $neg @('compute', 'network-endpoint-groups', 'describe', $neg, "--region=$Region") @('compute', 'network-endpoint-groups', 'create', $neg, "--region=$Region", '--network-endpoint-type=serverless', "--cloud-run-service=jobsnow-$service")
	Ensure $backend @('compute', 'backend-services', 'describe', $backend, '--global') @('compute', 'backend-services', 'create', $backend, '--global', '--load-balancing-scheme=EXTERNAL_MANAGED')
	$attached = & $gcloud compute backend-services describe $backend --global $projectArg '--format=value(backends[].group)' 2>$null
	if ("$attached" -notlike "*$neg*") {
		Run "ligar $neg" @('compute', 'backend-services', 'add-backend', $backend, '--global', "--network-endpoint-group=$neg", "--network-endpoint-group-region=$Region", $projectArg, '--quiet')
	}
}

Ensure 'mapa de URLs' @('compute', 'url-maps', 'describe', 'jobsnow-lb') @('compute', 'url-maps', 'create', 'jobsnow-lb', '--default-service=jobsnow-front-backend')

$hostRules = & $gcloud compute url-maps describe jobsnow-lb $projectArg '--format=value(hostRules[].hosts)' 2>$null
if ("$hostRules" -notlike "*api.$Domain*") {
	Run 'rota da vis' @('compute', 'url-maps', 'add-path-matcher', 'jobsnow-lb', '--path-matcher-name=vis', '--default-service=jobsnow-vis-backend', "--new-hosts=api.$Domain", $projectArg, '--quiet')
}
if ("$hostRules" -notlike "*login.$Domain*") {
	Run 'rota da js' @('compute', 'url-maps', 'add-path-matcher', 'jobsnow-lb', '--path-matcher-name=js', '--default-service=jobsnow-js-backend', "--new-hosts=login.$Domain", $projectArg, '--quiet')
}

$domains = "$Domain,www.$Domain,api.$Domain,login.$Domain"
Ensure 'certificado' @('compute', 'ssl-certificates', 'describe', 'jobsnow-cert', '--global') @('compute', 'ssl-certificates', 'create', 'jobsnow-cert', "--domains=$domains", '--global')
Ensure 'proxy https' @('compute', 'target-https-proxies', 'describe', 'jobsnow-https') @('compute', 'target-https-proxies', 'create', 'jobsnow-https', '--url-map=jobsnow-lb', '--ssl-certificates=jobsnow-cert')
Ensure 'regra 443' @('compute', 'forwarding-rules', 'describe', 'jobsnow-https', '--global') @('compute', 'forwarding-rules', 'create', 'jobsnow-https', '--global', '--load-balancing-scheme=EXTERNAL_MANAGED', "--address=$AddressName", '--target-https-proxy=jobsnow-https', '--ports=443')

$redirect = Join-Path $PSScriptRoot '09-redirecionar-http.yaml'
Ensure 'redirecionamento' @('compute', 'url-maps', 'describe', 'jobsnow-http-redirect') @('compute', 'url-maps', 'import', 'jobsnow-http-redirect', "--source=$redirect", '--global')
Ensure 'proxy http' @('compute', 'target-http-proxies', 'describe', 'jobsnow-http') @('compute', 'target-http-proxies', 'create', 'jobsnow-http', '--url-map=jobsnow-http-redirect')
Ensure 'regra 80' @('compute', 'forwarding-rules', 'describe', 'jobsnow-http', '--global') @('compute', 'forwarding-rules', 'create', 'jobsnow-http', '--global', '--load-balancing-scheme=EXTERNAL_MANAGED', "--address=$AddressName", '--target-http-proxy=jobsnow-http', '--ports=80')

'== situacao'
& $gcloud compute forwarding-rules list $projectArg '--format=table(name,IPAddress,portRange)' 2>&1 | ForEach-Object { "$_" }
& $gcloud compute url-maps describe jobsnow-lb $projectArg '--format=value(hostRules[].hosts)' 2>&1 | ForEach-Object { "hosts com regra: $_" }
& $gcloud compute ssl-certificates describe jobsnow-cert --global $projectArg '--format=yaml(managed.status,managed.domainStatus)' 2>&1 | ForEach-Object { "$_" }
