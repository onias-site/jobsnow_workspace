# Concede a conta de servico da VM apenas os papeis que os consumidores e o processo agendado usam.
# Rode depois de 01-criar-rede-e-vm.ps1.
param(
	[string]$Project = 'jobsnow-prd'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$serviceAccount = "jobsnow-vm@$Project.iam.gserviceaccount.com"

foreach ($role in 'roles/pubsub.subscriber', 'roles/pubsub.publisher', 'roles/secretmanager.secretAccessor', 'roles/logging.logWriter', 'roles/storage.objectAdmin') {
	& $gcloud projects add-iam-policy-binding $Project "--member=serviceAccount:$serviceAccount" "--role=$role" --condition=None --quiet *> $null
	if ($LASTEXITCODE -ne 0) { throw "falhou: papel $role" }
	Write-Output "ok $role"
}
