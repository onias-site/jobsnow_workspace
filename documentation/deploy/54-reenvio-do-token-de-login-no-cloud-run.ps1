# Reenvio diario do token de login (pedido do usuario em 2026-11-11): Cloud Run Job jobsnow-reenvio-token-login,
# disparado pelo Cloud Scheduler (o mesmo lugar do processo diario) de hora em hora (America/Sao_Paulo; era todo dia as 8h ate 2026-11-12). Roda
# JsBusinessResendLoginTokenToUsersWithoutPassword:
#   A) le no log de requisicoes do Cloud Run (jobsnow-js) os POST /login/{email}/token/language/{language} com 200 nas
#      ultimas 24 h;
#   B) recarrega as supressoes do SendGrid e tira os e-mails de jn_email_suppressed;
#   C) tira os e-mails de js_login_password;
#   D) roda JsServiceLogin.ResendLoginToken (o de POST /login/{email}/token/request/resending) para cada um que sobrou.
# Diferente do processo diario, o agendamento nasce ATIVO.
# Concessoes de IAM (rodar como administrador, como as demais): a conta jobsnow-vm@ precisa de roles/logging.viewer no
# projeto (passo A) e de roles/run.invoker no proprio job (o Cloud Scheduler dispara o job com ela).
# Pode rodar de novo: atualiza a imagem do job e o agendamento, e mantem a pausa (ou a retomada) que ja existir.
# Uso: .\54-reenvio-do-token-de-login-no-cloud-run.ps1 [-JarDoProcesso <cron.jar>] [-SemImagem] [-SoPermissoes]
#   -JarDoProcesso: outro jar (um montado so com o codigo ja comitado).
#   -SemImagem: mantem a imagem atual do job e so refaz configuracao, permissao e agendamento.
#   -SoPermissoes: so as duas concessoes de IAM (para o administrador).
# Rodar uma vez: gcloud run jobs execute jobsnow-reenvio-token-login --region southamerica-east1 --project=jobsnow-prd
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Repository = 'jobsnow',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$PropertiesSecret = 'jobsnow-application-properties',
	[string]$Job = 'jobsnow-reenvio-token-login',
	[string]$Schedule = '0 * * * *',
	[string]$TimeZone = 'America/Sao_Paulo',
	[string]$JarDoProcesso = '',
	[switch]$SemImagem,
	[switch]$SoPermissoes
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$registry = "$Region-docker.pkg.dev/$Project/$Repository"
$runtimeAccount = "jobsnow-vm@$Project.iam.gserviceaccount.com"
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'

function Run([string]$label, [string[]]$arguments) {
	Write-Host "== $label"
	& $gcloud @arguments 2>&1 | ForEach-Object { "$_" } | Select-Object -Last 6 | ForEach-Object { Write-Host $_ }
	if ($LASTEXITCODE -ne 0) { throw "falhou: $label" }
}

function Exists([string[]]$arguments) {
	& $gcloud @arguments *> $null
	return $LASTEXITCODE -eq 0
}

function GrantPermissions() {
	Run 'permissao de ler os logs (roles/logging.viewer)' @('projects', 'add-iam-policy-binding', $Project,
		"--member=serviceAccount:$runtimeAccount", '--role=roles/logging.viewer', '--condition=None', '--quiet')
	Run 'permissao de disparar o job' @('run', 'jobs', 'add-iam-policy-binding', $Job, "--project=$Project", "--region=$Region",
		"--member=serviceAccount:$runtimeAccount", '--role=roles/run.invoker', '--quiet')
}

if ($SoPermissoes) {
	GrantPermissions
	return
}

Run 'APIs do Cloud Scheduler, do Cloud Run e do Cloud Logging' @('services', 'enable', 'cloudscheduler.googleapis.com', 'run.googleapis.com', 'logging.googleapis.com', "--project=$Project", '--quiet')

$jobExists = Exists @('run', 'jobs', 'describe', $Job, "--project=$Project", "--region=$Region")
$image = ''
if ($SemImagem -and $jobExists) {
	$image = (& $gcloud run jobs describe $Job "--project=$Project" "--region=$Region" '--format=value(spec.template.spec.template.spec.containers[0].image)' 2>$null)
} else {
	$jar = $JarDoProcesso
	if (-not $jar) { $jar = Join-Path $workspace 'ccp_cron-tasks_jobsnow\target\ccp_cron-tasks_jobsnow-0.0.1-SNAPSHOT-all.jar' }
	$context = Join-Path $env:TEMP 'jobsnow-contexto-reenvio-token-login'
	if (Test-Path $context) { Remove-Item $context -Recurse -Force -Confirm:$false }
	New-Item -ItemType Directory $context | Out-Null
	Copy-Item $jar (Join-Path $context 'app.jar')
	Copy-Item (Join-Path $PSScriptRoot 'reenvio-do-token-de-login.Dockerfile') (Join-Path $context 'Dockerfile')
	$image = "$registry/reenvio-token-login:$tag"
	$config = Join-Path $PSScriptRoot '08-cloudbuild.yaml'
	Run 'imagem do reenvio do token de login' @('builds', 'submit', $context, "--project=$Project", "--region=$Region", "--config=$config", "--substitutions=_IMAGE=$image,_VIS_URL=,_LOGIN_URL=", '--quiet')
	Remove-Item $context -Recurse -Force -Confirm:$false
}

# uma tarefa, sem paralelismo, 30 min de limite e nenhuma nova tentativa: o servico recusa um pedido repetido (409),
# mas o suporte ja teria recebido os avisos da primeira tentativa. Mesma rede e conta das APIs (ES e Valkey da VPC).
Run "job $Job" @('run', 'jobs', 'deploy', $Job, "--image=$image", "--project=$Project", "--region=$Region",
	"--service-account=$runtimeAccount", '--memory=1Gi', '--cpu=1', '--tasks=1', '--parallelism=1', '--max-retries=0',
	'--task-timeout=1800s', "--network=$Network", "--subnet=$Subnet", '--vpc-egress=private-ranges-only',
	"--set-secrets=application_properties=${PropertiesSecret}:latest", '--quiet')

$uri = "https://run.googleapis.com/v2/projects/$Project/locations/$Region/jobs/${Job}:run"
$schedulerArguments = @($Job, "--project=$Project", "--location=$Region", "--schedule=$Schedule", "--time-zone=$TimeZone",
	"--uri=$uri", '--http-method=POST', "--oauth-service-account-email=$runtimeAccount", '--attempt-deadline=180s', '--quiet')
if (Exists @('scheduler', 'jobs', 'describe', $Job, "--project=$Project", "--location=$Region")) {
	Run 'agendamento (atualizado, estado mantido)' (@('scheduler', 'jobs', 'update', 'http') + $schedulerArguments)
} else {
	Run 'agendamento (ativo)' (@('scheduler', 'jobs', 'create', 'http') + $schedulerArguments)
}

'== situacao'
& $gcloud run jobs describe $Job "--project=$Project" "--region=$Region" '--format=value(metadata.name,spec.template.spec.template.spec.containers[0].image)' 2>&1 | ForEach-Object { "$_" }
& $gcloud scheduler jobs describe $Job "--project=$Project" "--location=$Region" '--format=value(schedule,timeZone,state)' 2>&1 | ForEach-Object { "$_" }
'== falta, se ainda nao foi feito: as concessoes de IAM, como administrador: .\54-reenvio-do-token-de-login-no-cloud-run.ps1 -SoPermissoes'
