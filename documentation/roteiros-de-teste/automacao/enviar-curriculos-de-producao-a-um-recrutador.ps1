# Envia a um unico recrutador o e-mail de curriculos com TODOS os vis_resume de producao (SendProductionResumesToRecruiter.java).
#   1. le producao, so leitura, pelo tunel IAP (ler-curriculos-de-producao.py) para um arquivo temporario;
#   2. compila o ccp_rest-api-tests_jobsnow e monta o classpath de teste;
#   3. roda o executor contra o Elasticsearch LOCAL, com a application_properties do ambiente trocando, so neste processo,
#      tokenEmailKey, urlEmailKey e recruiterLinksSecret pelos de C:\segredos\producao.json (sem o segredo de producao os
#      links "Ver curriculo" e de descadastro nao valem la). Nenhum valor e impresso.
#   4. so no modo enviar, aceito o e-mail: grava em producao, pelo tunel, a lista inteira da tela "ver todos"
#      (vis_recruiter_resumes, descartavel diario do recrutador), a unica gravacao em producao; sem ela o link "ver
#      todos" abria a tela vazia (corrigido em 2026-11-12).
# Os arquivos temporarios (curriculos de producao e lista) sao apagados no fim.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File enviar-curriculos-de-producao-a-um-recrutador.ps1 -Modo simular|enviar -Email <recrutador>
param(
	[Parameter(Mandatory = $true)][ValidateSet('simular', 'enviar')][string]$Modo,
	[Parameter(Mandatory = $true)][string]$Email,
	[string]$Front = 'https://onias.site',
	[string]$ApiVis = 'https://api.onias.site'
)
$ErrorActionPreference = 'Stop'
$automation = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $automation '..\..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$data = Join-Path $env:TEMP ("curriculos-de-producao-" + [guid]::NewGuid().ToString('N') + ".json")
$list = Join-Path $env:TEMP ("lista-ver-todos-" + [guid]::NewGuid().ToString('N') + ".json")
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $automation 'SendProductionResumesToRecruiter.java'
$localProperties = $env:application_properties
try {
	& (Join-Path $workspace 'documentation\deploy\com-tunel-de-producao.ps1') -Script (Join-Path $automation 'ler-curriculos-de-producao.py') -Argumentos $data
	if (-not (Test-Path $data)) { throw 'a leitura de producao nao gravou o arquivo' }

	Push-Location $tests
	try {
		$ErrorActionPreference = 'Continue'
		& cmd /c "mvn -o -q test-compile dependency:build-classpath -Dmdep.outputFile=target\create-entities-cp.txt -Dmdep.includeScope=test"
		if ($LASTEXITCODE -ne 0) { throw 'falha na compilacao do Maven' }
		$ErrorActionPreference = 'Stop'
		$classpath = (Get-Content -Raw 'target\create-entities-cp.txt').Trim() -replace '\\', '/'
		Set-Content -Encoding ascii 'target\create-entities-args.txt' ('-cp "target/test-classes;target/classes;' + $classpath + '"')

		$properties = $env:application_properties | ConvertFrom-Json
		$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
		foreach ($key in 'tokenEmailKey', 'urlEmailKey', 'recruiterLinksSecret') {
			if (-not $production.$key) { throw "C:\segredos\producao.json nao tem $key" }
			$properties | Add-Member -NotePropertyName $key -NotePropertyValue $production.$key -Force
		}
		$env:application_properties = $properties | ConvertTo-Json -Depth 20 -Compress
		$ErrorActionPreference = 'Continue'
		& $java -Xmx2g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor $Modo $Email $data $Front $ApiVis $list
		$result = $LASTEXITCODE

		$listToSave = ($Modo -eq 'enviar') -and ($result -eq 0) -and (Test-Path $list)
		if ($listToSave) {
			# o mesmo executor, agora com o Elasticsearch de producao (porta local do tunel e a credencial de producao)
			$productionProperties = $properties | ConvertTo-Json -Depth 20 | ConvertFrom-Json
			$productionProperties | Add-Member -NotePropertyName 'elasticsearch.address' -NotePropertyValue 'http://localhost:9210' -Force
			$productionSecret = $production.'elasticsearch.secret'
			if (-not $productionSecret) { $productionSecret = $production.elasticsearch.secret }
			if (-not $productionSecret) { throw 'C:\segredos\producao.json nao tem elasticsearch.secret' }
			$productionProperties | Add-Member -NotePropertyName 'elasticsearch.secret' -NotePropertyValue $productionSecret -Force
			$env:application_properties = $productionProperties | ConvertTo-Json -Depth 20 -Compress
			# o bloco roda dentro do com-tunel-de-producao.ps1, que tem o seu proprio escopo script: a saida do java volta
			# por esta hashtable, achada pelo escopo dinamico (um $script:x no bloco seria gravado no escopo do tunel)
			$listSaveState = @{ exitCode = 5 }
			$saveTheList = {
				& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor 'gravar-lista' $Email $list
				$listSaveState.exitCode = $LASTEXITCODE
			}
			& (Join-Path $workspace 'documentation\deploy\com-tunel-de-producao.ps1') -Bloco $saveTheList
			if ($listSaveState.exitCode -ne 0) { "a lista da tela ver todos NAO foi gravada em producao (saida $($listSaveState.exitCode))"; $result = 5 }
		}
	} finally {
		$env:application_properties = $localProperties
		Pop-Location
	}
} finally {
	Remove-Item $data -ErrorAction SilentlyContinue
	Remove-Item $list -ErrorAction SilentlyContinue
}
exit $result
