# Item E do deploy: cria um topico e uma assinatura pull para cada linha de topicos.tsv.
# Colunas: topico (nome completo da classe; a assinatura tem o mesmo nome, como CcpPubSubStarter espera),
# threads do consumidor e prazo de ack em segundos. Pode rodar de novo: pula o que ja existe.
param(
	[string]$Project = 'jobsnow-prd',
	[string]$Region = 'southamerica-east1'
)

$gcloud = Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd'
$topicsFile = Join-Path $PSScriptRoot 'topicos.tsv'
$created = 0

foreach ($line in (Get-Content $topicsFile | Where-Object { $_.Trim() })) {
	$columns = $line -split "`t"
	$topic = $columns[0]
	$ackDeadline = $columns[2]

	& $gcloud pubsub topics describe $topic --project $Project --format='value(name)' *> $null
	if ($LASTEXITCODE -ne 0) {
		& $gcloud pubsub topics create $topic --project $Project --message-storage-policy-allowed-regions=$Region --quiet *> $null
		if ($LASTEXITCODE -ne 0) { throw "falhou o topico $topic" }
		$created++
	}

	& $gcloud pubsub subscriptions describe $topic --project $Project --format='value(name)' *> $null
	if ($LASTEXITCODE -ne 0) {
		& $gcloud pubsub subscriptions create $topic --project $Project --topic=$topic --ack-deadline=$ackDeadline --message-retention-duration=7d --expiration-period=never --min-retry-delay=10s --max-retry-delay=600s --quiet *> $null
		if ($LASTEXITCODE -ne 0) { throw "falhou a assinatura $topic" }
		$created++
	}
}

Write-Output "criados agora: $created"
Write-Output "topicos: $((& $gcloud pubsub topics list --project $Project --format='value(name)').Count)"
Write-Output "assinaturas: $((& $gcloud pubsub subscriptions list --project $Project --format='value(name)').Count)"
