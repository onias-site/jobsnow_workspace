<#
.SYNOPSIS
    Mapeia o fecho transitivo de subtipos de um tipo Java (filhos diretos e indiretos).

.DESCRIPTION
    Monta o grafo de heranca a partir do codigo fonte e faz uma busca em largura a partir
    do tipo raiz. Um grep por "implements <Tipo>" acha so os filhos diretos; esta varredura
    acha tambem quem herda via interface intermediaria ou via classe-pai, em qualquer
    profundidade.

.PARAMETER Root
    Raiz do workspace a varrer. Padrao: C:\eclipse-workspaces\ccp

.PARAMETER Type
    Nome simples do tipo raiz. Padrao: CcpBusiness

.PARAMETER IncludeTests
    Inclui ccp_rest-api-tests_jobsnow na varredura. Por padrao fica de fora.

.PARAMETER Csv
    Caminho opcional para gravar o resultado em CSV.
#>
[CmdletBinding()]
param(
    [string] $Root = 'C:\eclipse-workspaces\ccp',
    [string] $Type = 'CcpBusiness',
    [switch] $IncludeTests,
    [string] $Csv
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Root)) { throw "Raiz nao encontrada: $Root" }

# ---------------------------------------------------------------- coleta de arquivos
$excluded = @('target', '.git', '.metadata', 'node_modules', 'bin')
if (-not $IncludeTests) { $excluded += 'ccp_rest-api-tests_jobsnow' }

$files = Get-ChildItem -Path $Root -Filter *.java -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($Root.Length).TrimStart('\', '/')
    $parts = $rel -split '[\\/]'
    -not ($parts | Where-Object { $excluded -contains $_ })
}

Write-Host "Arquivos .java varridos: $($files.Count)" -ForegroundColor DarkGray

# ---------------------------------------------------------------- parse das declaracoes
# (?<!@) descarta "@interface": declaracao de anotacao nao entra no grafo de heranca.
# Sem isso, uma anotacao homonima de um tipo real rouba o kind/arquivo dele.
$declRx = [regex] '(?<!@)\b(class|interface|enum|record)\s+([A-Za-z_]\w*)([^{;]*)\{'

$supers   = @{}   # tipo -> lista de supertipos (nome simples)
$kindOf   = @{}   # tipo -> class|interface|enum|record
$fileOf   = @{}   # tipo -> caminho relativo
$declTxt  = @{}   # tipo -> linha de declaracao normalizada

function Get-SupertypeNames {
    param([string] $Clause)

    # remove argumentos genericos, do mais interno para o mais externo,
    # senao Function<A,B> entregaria A e B como se fossem supertipos
    while ($Clause -match '<[^<>]*>') { $Clause = $Clause -replace '<[^<>]*>', '' }

    $names = @()
    foreach ($piece in ($Clause -split ',')) {
        $p = $piece.Trim()
        if (-not $p) { continue }
        # fica so com o nome simples de um eventual nome qualificado
        $simple = ($p -split '\.')[-1].Trim()
        if ($simple -match '^[A-Za-z_]\w*$') { $names += $simple }
    }
    return $names
}

foreach ($f in $files) {
    $src = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8
    if (-not $src) { continue }

    # tira comentarios e literais de string: senao a palavra "class" dentro de
    # um javadoc ou de uma string vira declaracao fantasma
    $src = $src -replace '(?s)/\*.*?\*/', ' '
    $src = $src -replace '//[^\r\n]*', ' '
    $src = $src -replace '"(\\.|[^"\\\r\n])*"', '""'

    $rel = $f.FullName.Substring($Root.Length).TrimStart('\', '/') -replace '\\', '/'

    foreach ($m in $declRx.Matches($src)) {
        $kind = $m.Groups[1].Value
        $name = $m.Groups[2].Value
        $tail = $m.Groups[3].Value

        $sup = @()
        if ($tail -match '(?s)\bextends\s+(.*?)(?=\bimplements\b|$)') {
            $sup += Get-SupertypeNames $Matches[1]
        }
        if ($tail -match '(?s)\bimplements\s+(.*)$') {
            $sup += Get-SupertypeNames $Matches[1]
        }
        $sup = $sup | Where-Object { $_ -notin @('extends', 'implements', 'super') }

        if (-not $supers.ContainsKey($name)) { $supers[$name] = @() }
        $supers[$name] += $sup

        if (-not $kindOf.ContainsKey($name)) {
            $kindOf[$name]  = $kind
            $fileOf[$name]  = $rel
            $declTxt[$name] = ($m.Value -replace '\s+', ' ').TrimEnd('{', ' ')
        }
    }
}

# ---------------------------------------------------------------- indice reverso + BFS
$children = @{}
foreach ($t in $supers.Keys) {
    foreach ($s in $supers[$t]) {
        if (-not $children.ContainsKey($s)) { $children[$s] = @() }
        $children[$s] += $t
    }
}

if (-not $children.ContainsKey($Type)) {
    Write-Warning "Nenhum subtipo encontrado para '$Type'. Confira o nome (usa-se o nome simples, sem pacote)."
}

$level = @{ $Type = 0 }
$queue = [System.Collections.Queue]::new()
$queue.Enqueue($Type)
$found = @{}

while ($queue.Count -gt 0) {
    $cur = $queue.Dequeue()
    foreach ($c in ($children[$cur] | Select-Object -Unique)) {
        if ($found.ContainsKey($c) -or $c -eq $Type) { continue }
        $found[$c]  = $true
        $level[$c]  = $level[$cur] + 1
        $queue.Enqueue($c)
    }
}

# ---------------------------------------------------------------- deteccao de colisao
$dupes = @{}
foreach ($t in $found.Keys) {
    $hits = @($files | Where-Object {
        $c = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
        $c -match "(?<!@)\b(class|interface|enum)\s+$([regex]::Escape($t))\b"
    })
    if ($hits.Count -gt 1) { $dupes[$t] = $hits.Count }
}

# ---------------------------------------------------------------- saida
$rows = foreach ($t in ($found.Keys | Sort-Object { $level[$_] }, { $_ })) {
    [pscustomobject]@{
        Nivel   = $level[$t]
        Kind    = $kindOf[$t]
        Tipo    = $t
        Modulo  = ($fileOf[$t] -split '/')[0]
        Arquivo = $fileOf[$t]
        Decl    = $declTxt[$t]
    }
}

# Format-Table emite objetos de formatacao; misturar com Write-Host na mesma
# sequencia quebra o out-lineoutput. Por isso a tabela vai por Out-String.
($rows | Format-Table Nivel, Kind, Tipo, Modulo -AutoSize | Out-String).TrimEnd() | Write-Host

Write-Host ''
Write-Host "TOTAL de subtipos de ${Type}: $($rows.Count)" -ForegroundColor Green
Write-Host ''
Write-Host 'Por nivel:' -ForegroundColor Cyan
$rows | Group-Object Nivel | Sort-Object Name |
    ForEach-Object { Write-Host ('  nivel {0}: {1}' -f $_.Name, $_.Count) }
Write-Host 'Por tipo de declaracao:' -ForegroundColor Cyan
$rows | Group-Object Kind | Sort-Object Count -Descending |
    ForEach-Object { Write-Host ('  {0}: {1}' -f $_.Name, $_.Count) }
Write-Host 'Por modulo:' -ForegroundColor Cyan
$rows | Group-Object Modulo | Sort-Object Count -Descending |
    ForEach-Object { Write-Host ('  {0}: {1}' -f $_.Name, $_.Count) }

if ($dupes.Count -gt 0) {
    Write-Host ''
    Write-Warning 'Nomes simples declarados em mais de um arquivo (o grafo pode ter fundido tipos distintos):'
    $dupes.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value) arquivos" }
} else {
    Write-Host ''
    Write-Host 'Colisao de nomes simples: nenhuma.' -ForegroundColor DarkGray
}

if ($Csv) {
    $rows | Export-Csv -LiteralPath $Csv -NoTypeInformation -Encoding UTF8
    Write-Host ''
    Write-Host "CSV gravado em $Csv" -ForegroundColor DarkGray
}
