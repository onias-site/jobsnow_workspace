# Item A do deploy: rede privada, firewall, conta de servico e a VM e2-standard-2 em southamerica-east1.
# A porta 9200 fica aberta so para a sub-rede privada, de onde o Cloud Run sai por Direct VPC egress.
# O SSH entra so pelo IAP (gcloud compute ssh --tunnel-through-iap). Pode rodar de novo: pula o que ja existe.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Zone = 'southamerica-east1-a',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$SubnetRange = '10.20.0.0/24',
	[string]$VmName = 'jobsnow-vm',
	[string]$MachineType = 'e2-standard-2',
	[int]$DiskGb = 50
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$ErrorActionPreference = 'Continue'

function Exists([string[]]$describe) {
	& $gcloud @describe --project $Project --format='value(name)' *> $null
	return $LASTEXITCODE -eq 0
}

function Run([string]$label, [string[]]$arguments) {
	Write-Output "--- $label"
	& $gcloud @arguments --project $Project --quiet 2>&1 | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw "falhou: $label" }
}

if (-not (Exists @('compute', 'networks', 'describe', $Network))) {
	Run 'rede' @('compute', 'networks', 'create', $Network, '--subnet-mode=custom')
}
if (-not (Exists @('compute', 'networks', 'subnets', 'describe', $Subnet, "--region=$Region"))) {
	Run 'sub-rede' @('compute', 'networks', 'subnets', 'create', $Subnet, "--network=$Network", "--region=$Region", "--range=$SubnetRange", '--enable-private-ip-google-access')
}
if (-not (Exists @('compute', 'firewall-rules', 'describe', 'jobsnow-allow-iap-ssh'))) {
	Run 'firewall ssh' @('compute', 'firewall-rules', 'create', 'jobsnow-allow-iap-ssh', "--network=$Network", '--direction=INGRESS', '--allow=tcp:22', '--source-ranges=35.235.240.0/20', '--target-tags=jobsnow-vm')
}
if (-not (Exists @('compute', 'firewall-rules', 'describe', 'jobsnow-allow-elasticsearch'))) {
	Run 'firewall elasticsearch' @('compute', 'firewall-rules', 'create', 'jobsnow-allow-elasticsearch', "--network=$Network", '--direction=INGRESS', '--allow=tcp:9200', "--source-ranges=$SubnetRange", '--target-tags=jobsnow-vm')
}

$serviceAccount = "jobsnow-vm@$Project.iam.gserviceaccount.com"
& $gcloud iam service-accounts describe $serviceAccount --project $Project --format='value(email)' *> $null
if ($LASTEXITCODE -ne 0) {
	Run 'conta de servico' @('iam', 'service-accounts', 'create', 'jobsnow-vm', '--display-name=JobsNow VM')
}
# Os papeis da conta de servico ficam em 01b-conceder-papeis.ps1, que o usuario roda ou aprova a parte.

if (-not (Exists @('compute', 'instances', 'describe', $VmName, "--zone=$Zone"))) {
	Run 'vm' @('compute', 'instances', 'create', $VmName, "--zone=$Zone", "--machine-type=$MachineType", "--subnet=$Subnet",
		'--image-family=ubuntu-2404-lts-amd64', '--image-project=ubuntu-os-cloud', "--boot-disk-size=${DiskGb}GB", '--boot-disk-type=pd-balanced',
		'--tags=jobsnow-vm', "--service-account=$serviceAccount", '--scopes=cloud-platform', '--shielded-secure-boot', '--shielded-vtpm', '--shielded-integrity-monitoring')
}

& $gcloud compute instances describe $VmName --zone=$Zone --project $Project --format='value(name,machineType.basename(),status,networkInterfaces[0].networkIP)' 2>&1 | ForEach-Object { "$_" }
