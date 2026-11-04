# libera as cotas do dia: marca no cache local a chave do registro e a da sua copia descartavel, depois apaga os dois
Add-Type -AssemblyName System.Numerics
$sha1 = [System.Security.Cryptography.SHA1]::Create()
function Mark([string]$key) {
  $bytes = [Text.Encoding]::UTF8.GetBytes($key)
  # como o Java: new BigInteger(sha1).toString(16), com sinal (hash com o 1o bit ligado vira '-' + o complemento)
  $digest = $sha1.ComputeHash($bytes); [array]::Reverse($digest)
  $big = [System.Numerics.BigInteger]::new([byte[]]($digest + [byte]0))
  if ($digest[$digest.Length - 1] -ge 128) { $big = $big - [System.Numerics.BigInteger]::Pow(2, 160); $name = '-' + ([System.Numerics.BigInteger]::Negate($big)).ToString('x').TrimStart('0') }
  else { $name = $big.ToString('x').TrimStart('0') }
  Set-Content -NoNewline -Path "c:\logs\cache\deleted-keys\$name" -Value ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
}
$ids = @((Invoke-RestMethod 'http://localhost:9200/jn_ticket_daily_limit/_search?size=1000&_source=false').hits.hits._id)
foreach ($id in $ids) { if ($id) { Mark "records.entity.jn_ticket_daily_limit.id.$id" } }
$copies = @((Invoke-RestMethod -Method Post -ContentType 'application/json' 'http://localhost:9200/jn_disposable_record/_search?size=1000&_source=false' -Body '{"query":{"term":{"entity":"jn_ticket_daily_limit"}}}').hits.hits._id)
foreach ($id in $copies) { if ($id) { Mark "records.entity.jn_disposable_record.id.$id" } }
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/jn_disposable_record/_delete_by_query?refresh=true' -Body '{"query":{"term":{"entity":"jn_ticket_daily_limit"}}}' | Out-Null
$r = Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/jn_ticket_daily_limit/_delete_by_query?refresh=true' -Body '{"query":{"match_all":{}}}'
"cotas liberadas: $($r.deleted), copias: $($copies.Count)"
