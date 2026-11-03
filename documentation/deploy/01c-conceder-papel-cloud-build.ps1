# Rodado pelo dono do projeto. Da a conta que o Cloud Build usa o papel de builder: ler o codigo enviado, gravar logs e publicar imagens.
param(
	[string]$Project = 'jobsnow-prd'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$projectNumber = & $gcloud projects describe $Project --format='value(projectNumber)'
$account = "$projectNumber-compute@developer.gserviceaccount.com"

& $gcloud projects add-iam-policy-binding $Project "--member=serviceAccount:$account" '--role=roles/cloudbuild.builds.builder' --condition=None --quiet --format='value(etag)' 2>&1 | ForEach-Object { "$_" }
if ($LASTEXITCODE -ne 0) { throw 'falhou ao conceder o papel' }
"ok: roles/cloudbuild.builds.builder para $account"
