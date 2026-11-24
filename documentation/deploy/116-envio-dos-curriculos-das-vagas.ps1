# Envio dos curriculos das vagas e divulgacao diaria das vagas nos grupos (2026-11-24):
#   1. cria em producao os indices vis_position_resumes (a lista "ver todos" do e-mail de cada vaga) e
#      vis_position_resume_sent (os pares vaga x curriculo ja enviados no envio instantaneo), com o mapeamento do local;
#   2. grava (SavePositionSendingSetup.java) os templates dos 2 e-mails das vagas ("Cv recebido para a vaga" e "{n} Cvs
#      recebidos para a vaga"), os parametros de envio adaptados (remetente e moreParameters copiados dos parametros do
#      e-mail diario aos recrutadores do mesmo Elasticsearch) e as mensagens do sistema da mensagem dos grupos;
#   3. com -Carga, regrava cada vaga ativa com mustSendInGroups: o decorator a poe nos grupos dos seus dias de divulgacao
#      (vis_virtual_position_publishing_day em jn_grouper), lidos pelo processo das 10h.
# Nenhum segredo e impresso. Idempotente. Sem -Gravar so cria os indices e conta.
# Ordem: rodar com -Gravar ANTES do deploy da vis, dos consumidores e do cron; com -Gravar -Carga DEPOIS do deploy da vis
# e dos consumidores (antes dele o codigo antigo nao poe a vaga nos grupos dos dias). Depois: cache das entidades de 1 h.
# -Local roda contra o Elasticsearch local (9200), sem tunel.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 116-envio-dos-curriculos-das-vagas.ps1 [-Gravar] [-Carga] [-Local]
param([switch]$Gravar, [switch]$Carga, [switch]$Local)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\SavePositionSendingSetup.java'
$createFolder = Join-Path $tests 'documentation\vis\database\elasticsearch\scripts\entities\create'
$localProperties = $env:application_properties
$state = @{ exitCode = 9 }

$createIndex = @'
import json, os, sys, urllib.error, urllib.request
target = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:9210"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(target + path, data=data, method=method, headers={"Content-Type": "application/json"})
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")
equal = True
for index in ("vis_position_resumes", "vis_position_resume_sent"):
    definition = json.load(open(os.path.join(sys.argv[1], index), encoding="utf-8"))
    status, _ = call("HEAD", "/" + index)
    if status == 404:
        status, answer = call("PUT", "/" + index, definition)
        print(index, "criado:", status, answer.get("acknowledged"))
    status, mapping = call("GET", "/" + index + "/_mapping")
    same = mapping[index]["mappings"]["properties"] == definition["mappings"]["properties"]
    print(index, "mapeamento igual ao do local:", same)
    equal = equal and same
sys.exit(0 if equal else 1)
'@

Push-Location $tests
try {
	$ErrorActionPreference = 'Continue'
	& cmd /c "mvn -o -q test-compile dependency:build-classpath -Dmdep.outputFile=target\create-entities-cp.txt -Dmdep.includeScope=test"
	if ($LASTEXITCODE -ne 0) { throw 'falha na compilacao do Maven' }
	$ErrorActionPreference = 'Stop'
	$classpath = (Get-Content -Raw 'target\create-entities-cp.txt').Trim() -replace '\\', '/'
	Set-Content -Encoding ascii 'target\create-entities-args.txt' ('-cp "target/test-classes;target/classes;' + $classpath + '"')

	$properties = $localProperties | ConvertFrom-Json
	$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
	$productionSecret = $production.'elasticsearch.secret'
	if (-not $productionSecret) { $productionSecret = $production.elasticsearch.secret }
	if (-not $productionSecret) { throw 'C:\segredos\producao.json nao tem elasticsearch.secret' }
	$properties | Add-Member -NotePropertyName 'elasticsearch.address' -NotePropertyValue 'http://localhost:9210' -Force
	$properties | Add-Member -NotePropertyName 'elasticsearch.secret' -NotePropertyValue $productionSecret -Force
	$productionProperties = $properties | ConvertTo-Json -Depth 20 -Compress

	$executorArguments = @()
	if ($Gravar) { $executorArguments += '--gravar' }
	if ($Carga) { $executorArguments += '--carga' }
	$inProduction = {
		$ErrorActionPreference = 'Continue'
		$createIndex | & python -I - $createFolder 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { $state.exitCode = 2; return }
		$env:application_properties = $productionProperties
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	if ($Local) {
		$ErrorActionPreference = 'Continue'
		$createIndex | & python -I - $createFolder 'http://127.0.0.1:9200' 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { $state.exitCode = 2 } else {
			& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
			$state.exitCode = $LASTEXITCODE
		}
	} else {
		& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $inProduction
	}
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"executor saiu com $($state.exitCode)"
exit $state.exitCode
