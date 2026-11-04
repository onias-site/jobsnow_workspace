# Reset do ES local preservando os dados carregados a pedido do usuario (vagas do Telegram e estatisticas, recrutadores,
# curriculos, grupos, supressoes do SendGrid e o historico de curriculos e recrutadores).
# Uso:  preservar-dados-no-reset.ps1 -Etapa salvar     copia cada indice para bkp_<indice>
#       (rodar executaCcpCreateEntities.bat)
#       preservar-dados-no-reset.ps1 -Etapa restaurar  devolve as copias aos indices recriados e apaga as copias
# So no ES local (localhost:9200). As APIs locais devem estar paradas (cache em memoria).
param([Parameter(Mandatory = $true)][ValidateSet('salvar', 'restaurar')][string]$Etapa)
$ErrorActionPreference = 'Stop'
$es = 'http://localhost:9200'
$cluster = (Invoke-RestMethod "$es/").cluster_name
if ($cluster -ne 'jobsnow-es9') { throw "cluster inesperado: $cluster (so roda no ES local)" }

$whole = @('vis_telegram_position', 'vis_statis_skill_line_chart', 'vis_statis_skill_pie_chart', 'vis_skill', 'vis_skill_dictionary',
	'vis_recruiter', 'vis_inactive_recruiter', 'vis_resume', 'vis_resume_linkedin', 'jn_grouper', 'jn_inactive_grouper',
	'jn_email_suppressed', 'jn_email_temporarily_blocked')
$versionableQuery = @{ terms = @{ entity = @('vis_resume', 'vis_inactive_resume', 'vis_recruiter', 'vis_inactive_recruiter') } }

function Reindex([string]$source, [string]$target, $query) {
	$body = @{ source = @{ index = $source; size = 5000 }; dest = @{ index = $target } }
	if ($query) { $body.source.query = $query }
	$json = $body | ConvertTo-Json -Depth 10
	$r = Invoke-RestMethod -Method Post "$es/_reindex?refresh=true&timeout=30m&slices=auto" -ContentType 'application/json' -Body $json -TimeoutSec 3600
	if ($r.failures.Count -gt 0) { throw "falhas no reindex $source -> ${target}: $($r.failures | ConvertTo-Json -Depth 4 -Compress)" }
	"$source -> ${target}: $($r.total) documentos"
}

function Count([string]$index) { (Invoke-RestMethod "$es/$index/_count").count }

if ($Etapa -eq 'salvar') {
	foreach ($index in $whole + @('jn_versionable')) {
		try { Invoke-RestMethod -Method Delete "$es/bkp_$index" | Out-Null } catch { }
	}
	foreach ($index in $whole) { Reindex $index "bkp_$index" $null }
	Reindex 'jn_versionable' 'bkp_jn_versionable' $versionableQuery
	return
}

foreach ($index in $whole) {
	$seeds = Count $index
	Invoke-RestMethod -Method Post "$es/$index/_delete_by_query?refresh=true&conflicts=proceed" -ContentType 'application/json' -Body '{"query":{"match_all":{}}}' | Out-Null
	"$index`: $seeds sementes apagadas"
	Reindex "bkp_$index" $index $null
}
Reindex 'bkp_jn_versionable' 'jn_versionable' $null
foreach ($index in $whole + @('jn_versionable')) {
	$backup = Count "bkp_$index"
	$restored = Count $index
	"conferencia $index`: copia $backup, indice $restored"
}
foreach ($index in $whole + @('jn_versionable')) { Invoke-RestMethod -Method Delete "$es/bkp_$index" | Out-Null }
'copias apagadas'
