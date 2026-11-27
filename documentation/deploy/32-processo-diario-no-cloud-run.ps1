# Processos agendados do cron.jar no Cloud Run, fora da VM (nao disputam a memoria da VM com o Elasticsearch e os
# consumidores). Desde 2026-11-17 a mesma imagem (processo-diario.Dockerfile) serve a dois Cloud Run Jobs, cada um com o
# seu agendamento no Cloud Scheduler (4 jobs desde 2026-11-24) e o processo (a classe) e a entrada JSON nos args do job:
#   jobsnow-backup-diario                todo dia as 00:10  JnBusinessBackupTheDatabase (backup por snapshot)
#   (desde 2026-11-24 o backup e seguido, no mesmo job, do e-mail diario dos curriculos das vagas de frequencia daily;
#   o processo aceita varios topicos separados por virgula, cada um roda mesmo que o anterior falhe)
#   jobsnow-curriculos-aos-recrutadores  de hora em hora, das 04:00 as 23:00, de segunda a sexta (desde 2026-11-27; antes todo
#                                        dia as 10:00)  VisBusinessSendResumesToRecruiters: cada execucao envia a 20a parte
#                                        de recruitersPerDay (100 de 2000) e pula quem ja recebeu no dia (e ainda pula sabado e domingo sozinho)
#   jobsnow-publicacao-das-vagas         todo dia as 10:00  VisBusinessPublishPositionsInTheGroups (vagas do dia nos grupos do bot user)
#   jobsnow-curriculos-semanais-das-vagas segunda as 09:30  VisBusinessSendWeeklyResumesOfThePositions (vagas de frequencia weekly)
#   jobsnow-vagas-do-bot-por-hora        de hora em hora, da 01:00 as 23:00 (desde 2026-11-26)  VisBusinessPublishJobPostingsOfTheHour:
#                                        as vagas do /salvarVaga do grupo da hora (vis_virtual_job_posting_hour) nos grupos de
#                                        tecnologia do bot user; sem nova tentativa (repetiria as mensagens nos grupos); a hora 0
#                                        nunca tem vaga (o grupo e sempre uma hora depois da gravacao)
# Antes de 2026-11-17 havia um job so, jobsnow-processo-diario, com VisBusinessDailyScheduledProcess (o e-mail e depois o
# backup) as 00:10; o backup virou jobsnow-backup-diario (Cloud Run nao renomeia: o script cria o novo e apaga o antigo
# e o seu agendamento, com o historico de execucoes). O expurgo dos disposable e as supressoes do SendGrid rodam de hora em hora no jobsnow-reenvio-token-login (54).
# Um agendamento que ja existe mantem a pausa (ou a retomada); um novo nasce ligado.
# Rodar uma vez:  gcloud run jobs execute <job> --region=southamerica-east1 --project=jobsnow-prd
# O crontab da VM nunca foi instalado; com os jobs, ele nao deve ser instalado.
# Concessoes de IAM: a conta jobsnow-vm@ dispara cada job (roles/run.invoker no proprio job) e quem roda este script
# precisa de iam.serviceAccounts.actAs sobre ela; como as demais concessoes, roda como administrador.
# Uso: .\32-processo-diario-no-cloud-run.ps1 [-JarDoProcesso <cron.jar>] [-SemImagem]
#   -JarDoProcesso: outro jar (um montado so com o codigo ja comitado, quando ha trabalho em andamento no workspace).
#   -SemImagem: mantem a imagem atual e so refaz configuracao, permissao e agendamento.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Repository = 'jobsnow',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$PropertiesSecret = 'jobsnow-application-properties',
	[string]$TimeZone = 'America/Sao_Paulo',
	[string]$JarDoProcesso = '',
	[switch]$SemImagem
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$registry = "$Region-docker.pkg.dev/$Project/$Repository"
$runtimeAccount = "jobsnow-vm@$Project.iam.gserviceaccount.com"
$tag = Get-Date -Format 'yyyyMMdd-HHmmss'
$receiver = '{"mensageriaReceiver":"com.jn.mensageria.JnMensageriaReceiver","operation":""}'

# cada job: nome, agendamento e processo (a classe executada pelo cron.jar)
$jobs = @(
	@{ Name = 'jobsnow-backup-diario'; Schedule = '10 0 * * *'; Process = 'com.jn.business.database.JnBusinessBackupTheDatabase,com.vis.business.recruiter.resumes.VisBusinessSendDailyResumesOfThePositions' },
	@{ Name = 'jobsnow-curriculos-aos-recrutadores'; Schedule = '0 4-23 * * 1-5'; Process = 'com.vis.business.recruiter.resumes.VisBusinessSendResumesToRecruiters' },
	@{ Name = 'jobsnow-publicacao-das-vagas'; Schedule = '0 10 * * *'; Process = 'com.vis.business.position.VisBusinessPublishPositionsInTheGroups' },
	@{ Name = 'jobsnow-curriculos-semanais-das-vagas'; Schedule = '30 9 * * 1'; Process = 'com.vis.business.recruiter.resumes.VisBusinessSendWeeklyResumesOfThePositions' },
	@{ Name = 'jobsnow-vagas-do-bot-por-hora'; Schedule = '0 1-23 * * *'; Process = 'com.vis.business.job.posting.VisBusinessPublishJobPostingsOfTheHour'; Retries = 0 }
)

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

$firstJob = $jobs[0].Name
$firstJobExists = Exists @('run', 'jobs', 'describe', $firstJob, "--project=$Project", "--region=$Region")
$image = ''
if ($SemImagem -and $firstJobExists) {
	$image = (& $gcloud run jobs describe $firstJob "--project=$Project" "--region=$Region" '--format=value(spec.template.spec.template.spec.containers[0].image)' 2>$null)
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

foreach ($definition in $jobs) {
	$job = $definition.Name
	# os args vao num arquivo de flags: o PowerShell 5.1 estraga as aspas da entrada JSON quando a passa ao gcloud.cmd
	$flagsFile = Join-Path $env:TEMP "jobsnow-args-$job.yaml"
	$yaml = "--args:`n- $($definition.Process)`n- '$receiver'`n"
	[System.IO.File]::WriteAllText($flagsFile, $yaml, (New-Object System.Text.UTF8Encoding $false))
	$jobArguments = "--flags-file=$flagsFile"
	# uma tarefa por execucao, sem paralelismo; 1 h de limite (o e-mail aos recrutadores e o snapshot passam dos 10 min
	# padrao) e uma nova tentativa se falhar (Retries muda, 0 no job que publica em grupos). Mesma rede e mesma conta das
	# APIs, para chegar ao ES e ao Valkey da VPC.
	$retries = if ($null -ne $definition.Retries) { $definition.Retries } else { 1 }
	Run "job $job" @('run', 'jobs', 'deploy', $job, "--image=$image", "--project=$Project", "--region=$Region", $jobArguments,
		"--service-account=$runtimeAccount", '--memory=1Gi', '--cpu=1', '--tasks=1', '--parallelism=1', "--max-retries=$retries",
		'--task-timeout=3600s', "--network=$Network", "--subnet=$Subnet", '--vpc-egress=private-ranges-only',
		"--set-secrets=application_properties=${PropertiesSecret}:latest", '--quiet')

	Run "permissao de disparar o job $job" @('run', 'jobs', 'add-iam-policy-binding', $job, "--project=$Project", "--region=$Region",
		"--member=serviceAccount:$runtimeAccount", '--role=roles/run.invoker', '--quiet')

	$uri = "https://run.googleapis.com/v2/projects/$Project/locations/$Region/jobs/${job}:run"
	$schedulerArguments = @($job, "--project=$Project", "--location=$Region", "--schedule=$($definition.Schedule)", "--time-zone=$TimeZone",
		"--uri=$uri", '--http-method=POST', "--oauth-service-account-email=$runtimeAccount", '--attempt-deadline=180s', '--quiet')
	if (Exists @('scheduler', 'jobs', 'describe', $job, "--project=$Project", "--location=$Region")) {
		Run "agendamento de $job (atualizado, estado mantido)" (@('scheduler', 'jobs', 'update', 'http') + $schedulerArguments)
	} else {
		Run "agendamento de $job" (@('scheduler', 'jobs', 'create', 'http') + $schedulerArguments)
	}
}

# jobs aposentados: apagados (agendamento e job) depois que os novos ja estao no ar
foreach ($retired in @('jobsnow-processo-diario')) {
	if (Exists @('scheduler', 'jobs', 'describe', $retired, "--project=$Project", "--location=$Region")) {
		Run "agendamento aposentado $retired" @('scheduler', 'jobs', 'delete', $retired, "--project=$Project", "--location=$Region", '--quiet')
	}
	if (Exists @('run', 'jobs', 'describe', $retired, "--project=$Project", "--region=$Region")) {
		Run "job aposentado $retired" @('run', 'jobs', 'delete', $retired, "--project=$Project", "--region=$Region", '--quiet')
	}
}

'== situacao'
foreach ($definition in $jobs) {
	$job = $definition.Name
	& $gcloud run jobs describe $job "--project=$Project" "--region=$Region" '--format=value(metadata.name,spec.template.spec.template.spec.containers[0].image,spec.template.spec.template.spec.containers[0].args)' 2>&1 | ForEach-Object { "$_" }
	& $gcloud scheduler jobs describe $job "--project=$Project" "--location=$Region" '--format=value(schedule,timeZone,state)' 2>&1 | ForEach-Object { "$_" }
}
