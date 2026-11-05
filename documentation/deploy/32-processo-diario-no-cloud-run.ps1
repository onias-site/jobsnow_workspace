# Tira o processo diario (VisBusinessDailyScheduledProcess: carga das supressoes do SendGrid, e-mail de curriculos aos
# recrutadores, expurgo dos disposable e backup por snapshot) da VM: vira o Cloud Run Job jobsnow-processo-diario,
# disparado pelo Cloud Scheduler, e deixa de disputar a memoria da VM com o Elasticsearch e os consumidores.
# O agendamento nasce PAUSADO (decisao do usuario em 2026-11-04): o envio aos recrutadores so comeca por ordem dele.
# Para ligar:     gcloud scheduler jobs resume jobsnow-processo-diario --location=southamerica-east1 --project=jobsnow-prd
# Rodar uma vez:  gcloud run jobs execute jobsnow-processo-diario --region=southamerica-east1 --project=jobsnow-prd
# O horario e o mesmo de 06-agendamento.cron (22h de segunda a sexta, America/Sao_Paulo). O crontab da VM nunca foi
# instalado; com o job, ele nao deve ser instalado.
# Pode rodar de novo: atualiza a imagem do job e o agendamento, e mantem a pausa (ou a retomada) que ja existir.
# Concessoes de IAM: a conta jobsnow-vm@ dispara o job (roles/run.invoker no proprio job) e quem roda este script precisa
# de iam.serviceAccounts.actAs sobre ela; como as demais concessoes, roda como administrador.
# Uso: .\32-processo-diario-no-cloud-run.ps1 [-JarDoProcesso <cron.jar>] [-SemImagem]
#   -JarDoProcesso: outro jar (um montado so com o codigo ja comitado, quando ha trabalho em andamento no workspace).
#   -SemImagem: mantem a imagem atual do job e so refaz configuracao, permissao e agendamento.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Repository = 'jobsnow',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$PropertiesSecret = 'jobsnow-application-properties',
	[string]$Job = 'jobsnow-processo-diario',
	[string]$Schedule = '0 22 * * 1-5',
	[string]$TimeZone = 'America/Sao_Paulo',
	[string]$JarDoProcesso = '',
	[switch]$SemImagem
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

Run 'APIs do Cloud Scheduler e do Cloud Run' @('services', 'enable', 'cloudscheduler.googleapis.com', 'run.googleapis.com', "--project=$Project", '--quiet')

$jobExists = Exists @('run', 'jobs', 'describe', $Job, "--project=$Project", "--region=$Region")
$image = ''
if ($SemImagem -and $jobExists) {
	$image = (& $gcloud run jobs describe $Job "--project=$Project" "--region=$Region" '--format=value(spec.template.spec.template.spec.containers[0].image)' 2>$null)
} else {
	$jar = $JarDoProcesso
	if (-not $jar) { $jar = Join-Path $workspace 'ccp_cron-tasks_jobsnow\target\ccp_cron-tasks_jobsnow-0.0.1-SNAPSHOT-all.jar' }
	$context = Join-Path $env:TEMP 'jobsnow-contexto-processo-diario'
	if (Test-Path $context) { Remove-Item $context -Recurse -Force -Confirm:$false }
	New-Item -ItemType Directory $context | Out-Null
	Copy-Item $jar (Join-Path $context 'app.jar')
	Copy-Item (Join-Path $PSScriptRoot 'processo-diario.Dockerfile') (Join-Path $context 'Dockerfile')
	$image = "$registry/processo-diario:$tag"
	$config = Join-Path $PSScriptRoot '08-cloudbuild.yaml'
	Run 'imagem do processo diario' @('builds', 'submit', $context, "--project=$Project", "--region=$Region", "--config=$config", "--substitutions=_IMAGE=$image,_VIS_URL=,_LOGIN_URL=", '--quiet')
	Remove-Item $context -Recurse -Force -Confirm:$false
}

# uma tarefa por execucao, sem paralelismo; 1 h de limite (o e-mail aos recrutadores e o snapshot passam dos 10 min
# padrao) e uma nova tentativa se falhar. Mesma rede e mesma conta das APIs, para chegar ao ES e ao Valkey da VPC.
Run "job $Job" @('run', 'jobs', 'deploy', $Job, "--image=$image", "--project=$Project", "--region=$Region",
	"--service-account=$runtimeAccount", '--memory=1Gi', '--cpu=1', '--tasks=1', '--parallelism=1', '--max-retries=1',
	'--task-timeout=3600s', "--network=$Network", "--subnet=$Subnet", '--vpc-egress=private-ranges-only',
	"--set-secrets=application_properties=${PropertiesSecret}:latest", '--quiet')

Run 'permissao de disparar o job' @('run', 'jobs', 'add-iam-policy-binding', $Job, "--project=$Project", "--region=$Region",
	"--member=serviceAccount:$runtimeAccount", '--role=roles/run.invoker', '--quiet')

$uri = "https://run.googleapis.com/v2/projects/$Project/locations/$Region/jobs/${Job}:run"
$schedulerArguments = @($Job, "--project=$Project", "--location=$Region", "--schedule=$Schedule", "--time-zone=$TimeZone",
	"--uri=$uri", '--http-method=POST', "--oauth-service-account-email=$runtimeAccount", '--attempt-deadline=180s', '--quiet')
if (Exists @('scheduler', 'jobs', 'describe', $Job, "--project=$Project", "--location=$Region")) {
	Run 'agendamento (atualizado, estado mantido)' (@('scheduler', 'jobs', 'update', 'http') + $schedulerArguments)
} else {
	Run 'agendamento' (@('scheduler', 'jobs', 'create', 'http') + $schedulerArguments)
	Run 'agendamento pausado' @('scheduler', 'jobs', 'pause', $Job, "--project=$Project", "--location=$Region", '--quiet')
}

'== situacao'
& $gcloud run jobs describe $Job "--project=$Project" "--region=$Region" '--format=value(metadata.name,spec.template.spec.template.spec.containers[0].image)' 2>&1 | ForEach-Object { "$_" }
& $gcloud scheduler jobs describe $Job "--project=$Project" "--location=$Region" '--format=value(schedule,timeZone,state)' 2>&1 | ForEach-Object { "$_" }
