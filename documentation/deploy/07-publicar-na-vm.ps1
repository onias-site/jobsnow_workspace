# Publica na VM as propriedades de producao e, sem -SemJars, os jars dos consumidores e do processo agendado.
# Depois de alterar C:\segredos\producao.json basta rodar com -SemJars. Nenhum valor secreto vai para a tela nem para a linha de comando.
# Com -SoConsumidores vai so o jar dos consumidores e o cron.jar da VM fica como esta; -JarDosConsumidores aponta outro jar
# (por exemplo, um montado so com o codigo ja comitado, quando ha trabalho em andamento no workspace).
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Zone = 'southamerica-east1-a',
	[string]$VmName = 'jobsnow-vm',
	[string]$PropertiesFile = 'C:\segredos\producao.json',
	[switch]$SemJars,
	[switch]$SoConsumidores,
	[string]$JarDosConsumidores = ''
)

$ErrorActionPreference = 'Stop'
$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$workspace = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$remote = "/tmp/jobsnow-publicacao-$([guid]::NewGuid().ToString('N'))"
$sshArgs = @("--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet')

function Run-OnVm([string]$label, [string]$command) {
	& cmd /c "`"$gcloud`" compute ssh $VmName $($sshArgs -join ' ') --command=`"$command`" 2>&1" | ForEach-Object { "$_" }
	if ($LASTEXITCODE -ne 0) { throw "falhou: $label" }
}

function Copy-ToVm([string]$label, [string]$source, [string]$name) {
	$started = Get-Date
	& cmd /c "`"$gcloud`" compute scp $($sshArgs -join ' ') `"$source`" ${VmName}:$remote/$name >nul 2>&1"
	if ($LASTEXITCODE -ne 0) { throw "falhou ao copiar $label" }
	"copiado: $label ($([int]((Get-Date) - $started).TotalSeconds) s)"
}

Get-Content $PropertiesFile -Raw | ConvertFrom-Json | Out-Null

Run-OnVm 'criar a pasta temporaria' "install -d -m 700 $remote"
Copy-ToVm 'propriedades' $PropertiesFile 'producao.json'
foreach ($name in 'ambiente.sh', 'topicos.tsv', '05-consumidores.config.js', '05-iniciar-consumidores.sh', '06-rodar-processo-diario.sh', '07-publicar-na-vm.sh') {
	Copy-ToVm $name (Join-Path $PSScriptRoot $name) $name
}

if (-not $SemJars) {
	$consumers = Join-Path $workspace 'ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser\target\ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser-0.0.1-SNAPSHOT-all.jar'
	$cron = Join-Path $workspace 'ccp_cron-tasks_jobsnow\target\ccp_cron-tasks_jobsnow-0.0.1-SNAPSHOT-all.jar'
	if ($JarDosConsumidores) { $consumers = $JarDosConsumidores }
	Copy-ToVm 'jar dos consumidores' $consumers 'consumidores.jar'
	if (-not $SoConsumidores) { Copy-ToVm 'jar do processo agendado' $cron 'cron.jar' }
}

Run-OnVm 'instalar' "sudo bash $remote/07-publicar-na-vm.sh $remote"
