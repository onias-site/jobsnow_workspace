# Roda o java com a application_properties do ambiente, trocando so a chave e o endereco do SendGrid (tokenEmailKey e
# urlEmailKey) pelos de C:\segredos\producao.json: a chave da application_properties local da 401 no SendGrid. A troca
# vale so para este processo; nenhum valor e impresso. O resto (Elasticsearch etc.) continua o local.
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File com-chave-do-sendgrid.ps1 <argumentos do java>
$ErrorActionPreference = 'Stop'
$properties = $env:application_properties | ConvertFrom-Json
$production = Get-Content 'C:\segredos\producao.json' -Raw | ConvertFrom-Json
foreach ($key in 'tokenEmailKey', 'urlEmailKey') {
	$properties | Add-Member -NotePropertyName $key -NotePropertyValue $production.$key -Force
}
$env:application_properties = $properties | ConvertTo-Json -Depth 20 -Compress
& 'C:\Program Files\Java\jdk-17\bin\java.exe' @args
exit $LASTEXITCODE
