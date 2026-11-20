# Aplica no vis_skill de producao (2026-11-20, pedido do usuario: "aprovacoes sempre vao alterar o vis_skill e seus
# agrupamentos") toda decisao aprovada que ainda nao esta la: itens de hierarquia aprovados
# (vis_skill_fix_hierarchy_item_approved: o parent entra na associacao e sai na desassociacao) e sugestoes de habilidade
# aprovadas (vis_skill_approved: a skill com os sinonimos sugeridos). Na leitura de 2026-11-20 faltavam
# NOSQLDATABASE em MEMCACHE e JAVA SERVER em JERSEY.
# O ApplyApprovedSkillDecisions.java roda os mesmos businesses do bot (VisBusinessSkillFixHierarchyItem e
# VisBusinessSkillSuggestionApply), que gravam pela entidade VisEntitySkill: o save atualiza os agrupamentos de iniciais
# do jn_grouper (@CcpStoredParentIdsField) e o dicionario (vis_skill_dictionary). Idempotente.
# Sem -Gravar so mostra o que falta. Depois: o cache (Memorystore) das APIs guarda as skills lidas por ate 1 hora.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 103-aplica-aprovacoes-no-vis-skill.ps1 [-Gravar]
param([switch]$Gravar)
$ErrorActionPreference = 'Stop'
$deploy = $PSScriptRoot
$workspace = (Resolve-Path (Join-Path $deploy '..\..')).Path
$tests = Join-Path $workspace 'ccp_rest-api-tests_jobsnow'
$java = 'C:\Program Files\Java\jdk-17\bin\java.exe'
$executor = Join-Path $workspace 'documentation\roteiros-de-teste\automacao\ApplyApprovedSkillDecisions.java'
$localProperties = $env:application_properties
$state = @{ exitCode = 9 }
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
	$applyInProduction = {
		$ErrorActionPreference = 'Continue'
		$env:application_properties = $productionProperties
		& $java -Xmx1g '-Dfile.encoding=UTF-8' '@target\create-entities-args.txt' $executor @executorArguments 2>&1 | Where-Object { "$_" -notmatch 'Commons Logging' } | ForEach-Object { "$_" }
		$state.exitCode = $LASTEXITCODE
		$env:application_properties = $localProperties
	}
	& (Join-Path $deploy 'com-tunel-de-producao.ps1') -Bloco $applyInProduction
} finally {
	$env:application_properties = $localProperties
	Pop-Location
}
"saiu com $($state.exitCode)"
exit $state.exitCode
