# Itens J, K e L do deploy: gera as imagens no Cloud Build e publica front, vis e js no Cloud Run, com acesso privado.
# Os jars vem de um mvn install anterior. As propriedades vao do arquivo local para o Secret Manager, sem passar pela tela.
# Sem -Servicos publica os tres. -SoSegredo guarda as propriedades e publica revisoes novas com a imagem atual.
# -ManterSegredo publica o codigo sem criar outra versao das propriedades. Quem ja existe mantem o acesso (publico ou privado)
# e a instancia minima, salvo -MinimoJs; servico novo nasce privado e com minimo zero.
# -JarDaJs / -JarDaVis publicam um jar gerado fora do target (build isolado, sem trabalho local em andamento).
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1',
	[string]$Repository = 'jobsnow',
	[string]$Network = 'jobsnow-vpc',
	[string]$Subnet = 'jobsnow-subnet',
	[string]$PropertiesFile = 'C:\segredos\producao.json',
	[string]$PropertiesSecret = 'jobsnow-application-properties',
	[string]$VisUrl = 'https://api.onias.site',
	[string]$LoginUrl = 'https://login.onias.site',
	[string[]]$Servicos = @('vis', 'js', 'front'),
	[int]$MinimoJs = -1,
	[switch]$SoSegredo,
	[switch]$ManterSegredo,
	[string]$JarDaJs = '',
	[string]$JarDaVis = ''
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

function Build([string]$service, [string]$context) {
	$image = "$registry/${service}:$tag"
	$config = Join-Path $PSScriptRoot '08-cloudbuild.yaml'
	Run "imagem de $service" @('builds', 'submit', $context, "--project=$Project", "--region=$Region", "--config=$config", "--substitutions=_IMAGE=$image,_VIS_URL=$VisUrl,_LOGIN_URL=$LoginUrl", '--quiet')
	return $image
}

function Prepare-ApiContext([string]$service, [string]$artifact) {
	$context = Join-Path $env:TEMP "jobsnow-contexto-$service"
	if (Test-Path $context) { Remove-Item $context -Recurse -Force -Confirm:$false }
	New-Item -ItemType Directory $context | Out-Null
	$jar = Join-Path $workspace $artifact
	if ($service -eq 'js' -and $JarDaJs) { $jar = $JarDaJs }
	if ($service -eq 'vis' -and $JarDaVis) { $jar = $JarDaVis }
	Write-Host "== jar de ${service}: $jar"
	Copy-Item $jar (Join-Path $context 'app.jar')
	Copy-Item (Join-Path $PSScriptRoot 'api.Dockerfile') (Join-Path $context 'Dockerfile')
	return $context
}

function Deploy-Api([string]$service, [string]$image, [int]$port, [int]$minimum) {
	$arguments = @('run', 'deploy', "jobsnow-$service", "--image=$image", "--project=$Project", "--region=$Region",
		"--service-account=$runtimeAccount", "--port=$port", '--memory=1Gi', '--cpu=1', '--cpu-boost', '--max-instances=3',
		"--network=$Network", "--subnet=$Subnet", '--vpc-egress=private-ranges-only',
		"--set-secrets=application_properties=${PropertiesSecret}:latest",
		'--update-env-vars=SPRINGDOC_API_DOCS_ENABLED=false,SPRINGDOC_SWAGGER_UI_ENABLED=false', '--quiet')
	if ($minimum -ge 0) { $arguments += "--min-instances=$minimum" }
	Run "servico jobsnow-$service" $arguments
}

function Current-Image([string]$service) {
	return (& $gcloud run services describe "jobsnow-$service" "--project=$Project" "--region=$Region" '--format=value(spec.template.spec.containers[0].image)' 2>$null)
}

$ports = @{ vis = 8081; js = 8082 }
$artifacts = @{
	vis = 'vis_rest-api_spring_jobsnow_dependency-chooser\target\jn_rest-api_spring_jobsnow_dependency-chooser.war'
	js = 'js_rest-api_spring_jobsnow_dependency-chooser\target\js_rest-api_spring_jobsnow_dependency-chooser-0.0.1-SNAPSHOT.jar'
}

Get-Content $PropertiesFile -Raw | ConvertFrom-Json | Out-Null
if (-not (Exists @('artifacts', 'repositories', 'describe', $Repository, "--location=$Region", "--project=$Project"))) {
	Run 'repositorio de imagens' @('artifacts', 'repositories', 'create', $Repository, '--repository-format=docker', "--location=$Region", "--project=$Project", '--quiet')
}
$secretExists = Exists @('secrets', 'describe', $PropertiesSecret, "--project=$Project")
if ($secretExists -and $ManterSegredo) {
	Write-Host 'propriedades mantidas na versao atual'
} elseif ($secretExists) {
	Run 'nova versao das propriedades' @('secrets', 'versions', 'add', $PropertiesSecret, "--data-file=$PropertiesFile", "--project=$Project", '--quiet')
} else {
	Run 'segredo das propriedades' @('secrets', 'create', $PropertiesSecret, '--replication-policy=user-managed', "--locations=$Region", "--data-file=$PropertiesFile", "--project=$Project", '--quiet')
}

foreach ($service in $Servicos) {
	$minimum = -1
	if ($service -eq 'js') { $minimum = $MinimoJs }

	if ($SoSegredo) {
		if ($service -eq 'front') { continue }
		$current = Current-Image $service
		Deploy-Api $service $current $ports[$service] $minimum
		continue
	}

	if ($service -eq 'front') {
		$frontImage = Build 'front' (Join-Path $workspace 'jn_frontend_calistrato-react')
		Run 'servico jobsnow-front' @('run', 'deploy', 'jobsnow-front', "--image=$frontImage", "--project=$Project", "--region=$Region",
			"--service-account=$runtimeAccount", '--port=8080', '--memory=512Mi', '--cpu=1', '--max-instances=3', '--quiet')
		continue
	}

	$context = Prepare-ApiContext $service $artifacts[$service]
	$apiImage = Build $service $context
	Remove-Item $context -Recurse -Force -Confirm:$false
	Deploy-Api $service $apiImage $ports[$service] $minimum
}

'== servicos'
& $gcloud run services list "--project=$Project" "--region=$Region" '--format=table(metadata.name,status.url,status.conditions[0].status)' 2>&1 | ForEach-Object { "$_" }
