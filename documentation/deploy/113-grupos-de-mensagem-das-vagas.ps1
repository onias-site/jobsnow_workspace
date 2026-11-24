# Cria em producao o indice vis_position_instant_message_group (2026-11-23), a entidade nova
# VisEntityPositionInstantMessageGroup: os grupos de mensagem instantanea onde a vaga e divulgada, um registro por
# senioridade, area (resumeType) e ddd, com os chats dos grupos e o bot (user). Depois grava os grupos de vagas do dono do
# site em que o bot user de producao entrou, um por area: o cartesiano de todas as senioridades com todos os ddds para a
# area de cada grupo (SavePositionInstantMessageGroups.java, pelo save da entidade, com os decorators).
#   1. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   2. abre o tunel de producao: cria o indice com o mapeamento do local (se ja existir, so confere) e roda o executor com
#      a application_properties do ambiente trocando, so neste processo, o Elasticsearch pelo do tunel.
# Nenhum segredo e impresso. Idempotente: o executor sobrescreve os mesmos registros.
# Sem -Gravar so cria o indice e mostra quantos registros cada area teria.
# Roda ANTES do deploy da API que ler o indice. Depois: o cache das entidades dura 1 hora.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 113-grupos-de-mensagem-das-vagas.ps1 -Grupos 1=<chatId>,2=<chatId>,3=<chatId>,4=<chatId> [-Gravar]
param([Parameter(Mandatory=$true)][string[]]$Grupos, [switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\SavePositionInstantMessageGroups.java'
$createFile = Join-Path $tests 'documentation\vis\database\elasticsearch\scripts\entities\create\vis_position_instant_message_group'
$localProperties = $env:application_properties
$state = @{ exitCode = 9 }

$createIndex = @'
import json, os, sys, urllib.error, urllib.request
index = "vis_position_instant_message_group"
definition = json.load(open(sys.argv[1], encoding="utf-8"))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request("http://127.0.0.1:9210" + path, data=data, method=method, headers={"Content-Type": "application/json"})
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")
status, _ = call("HEAD", "/" + index)
if status == 404:
    status, answer = call("PUT", "/" + index, definition)
    print("indice criado:", status, answer.get("acknowledged"))
status, mapping = call("GET", "/" + index + "/_mapping")
properties = mapping[index]["mappings"]["properties"]
expected = definition["mappings"]["properties"]
print("mapeamento igual ao do local:", properties == expected)
sys.exit(0 if properties == expected else 1)
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

	# com -File o PowerShell nao separa a lista por virgula: chega um texto so
	$executorArguments = @($Grupos | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
	if ($Gravar) { $executorArguments += '--gravar' }
	$inProduction = {
		$ErrorActionPreference = 'Continue'
		$createIndex | & python -I - $createFile 2>&1 | ForEach-Object { "$_" }
		if ($LASTEXITCODE -ne 0) { $state.exitCode = 2; return }
		$env:application_properties = $productionProperties
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $inProduction
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"executor saiu com $($state.exitCode)"
exit $state.exitCode
