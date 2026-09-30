# Mapeia todas as strings literais dos arquivos .java e agrupa por "razao de existir".
#
#   .\map-literals.ps1 [-Root <dir>] [-OutDir <dir>] [-Top <n>]
#
# Gera no OutDir:
#   literals.csv  - um registro por literal, com o contexto sintatico cru (antes e depois)
#   final.csv     - o mesmo, ja classificado por razao / subcategoria / centro de custo
# e imprime o relatorio agregado em stdout.

param(
    [string] $Root   = 'C:\eclipse-workspaces\ccp',
    [string] $OutDir = $(Join-Path $env:TEMP 'map-literals'),
    [int]    $Top    = 12
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

# ─── 1. Coleta de arquivos ────────────────────────────────────────────────────
# ccp_rest-api-tests_jobsnow fica de fora: e o projeto de testes, nao codigo de producao.
$files = Get-ChildItem -Path $Root -Filter *.java -Recurse -File | Where-Object {
    $p = $_.FullName
    ($p -notmatch '\\target\\') -and
    ($p -notmatch '\\node_modules\\') -and
    ($p -notmatch '\\ccp_rest-api-tests_jobsnow\\') -and
    ($p -notmatch '\\bin\\')
}

# ─── 2. Tokenizacao ───────────────────────────────────────────────────────────
# Maquina de estados que ignora comentarios de linha e de bloco, literais de char e
# escapes, e entende text blocks (\"\"\"). Cada caractere consumido e substituido por um
# espaco num buffer paralelo ($code) de MESMO comprimento, preservando as quebras de
# linha. Assim a varredura para tras nunca tropeca em parenteses que estejam dentro de
# comentario ou de string, e o indice continua servindo para calcular a linha.
$records = New-Object System.Collections.ArrayList

foreach ($f in $files) {
    $src = [System.IO.File]::ReadAllText($f.FullName)
    $n = $src.Length
    $i = 0
    $code = New-Object System.Text.StringBuilder
    $lits = New-Object System.Collections.ArrayList

    while ($i -lt $n) {
        $c = $src[$i]
        $c2 = if ($i + 1 -lt $n) { $src[$i + 1] } else { [char]0 }

        if ($c -eq '/' -and $c2 -eq '/') {
            while ($i -lt $n -and $src[$i] -ne "`n") { [void]$code.Append(' '); $i++ }
            continue
        }
        if ($c -eq '/' -and $c2 -eq '*') {
            [void]$code.Append('  '); $i += 2
            while ($i -lt $n -and -not ($src[$i] -eq '*' -and ($i + 1 -lt $n) -and $src[$i + 1] -eq '/')) {
                if ($src[$i] -eq "`n") { [void]$code.Append("`n") } else { [void]$code.Append(' ') }
                $i++
            }
            [void]$code.Append('  '); $i += 2
            continue
        }
        if ($c -eq "'") {
            [void]$code.Append(' '); $i++
            while ($i -lt $n -and $src[$i] -ne "'") {
                if ($src[$i] -eq '\') { [void]$code.Append(' '); $i++ }
                if ($i -lt $n) { [void]$code.Append(' '); $i++ }
            }
            [void]$code.Append(' '); $i++
            continue
        }
        if ($c -eq '"') {
            $isBlock = ($i + 2 -lt $n) -and ($src[$i + 1] -eq '"') -and ($src[$i + 2] -eq '"')
            $startPos = $code.Length
            $val = New-Object System.Text.StringBuilder
            if ($isBlock) {
                [void]$code.Append('   '); $i += 3
                while ($i -lt $n) {
                    if ($src[$i] -eq '"' -and ($i + 2 -lt $n) -and $src[$i + 1] -eq '"' -and $src[$i + 2] -eq '"') { break }
                    [void]$val.Append($src[$i])
                    if ($src[$i] -eq "`n") { [void]$code.Append("`n") } else { [void]$code.Append(' ') }
                    $i++
                }
                [void]$code.Append('   '); $i += 3
            } else {
                [void]$code.Append(' '); $i++
                while ($i -lt $n -and $src[$i] -ne '"') {
                    if ($src[$i] -eq '\') { [void]$val.Append($src[$i]); [void]$code.Append(' '); $i++ }
                    if ($i -lt $n) { [void]$val.Append($src[$i]); [void]$code.Append(' '); $i++ }
                }
                [void]$code.Append(' '); $i++
            }
            [void]$lits.Add([pscustomobject]@{ Pos = $startPos; Value = $val.ToString(); Block = $isBlock })
            continue
        }
        [void]$code.Append($c)
        $i++
    }

    $codeStr = $code.ToString()

    foreach ($lit in $lits) {
        $pos = $lit.Pos

        # Varredura para tras: acha o '(' nao-balanceado mais proximo e identifica quem o
        # precede -> @Anotacao, new Tipo, .metodo ou chamada simples. E isso que revela o
        # papel do literal. Para no ';' / '{' / '}' porque ali a expressao ja terminou.
        $depth = 0
        $j = $pos - 1
        $ownerKind = 'none'
        $ownerName = ''
        while ($j -ge 0) {
            $ch = $codeStr[$j]
            if ($ch -eq ')' -or $ch -eq ']') { $depth++ }
            elseif ($ch -eq '(') {
                if ($depth -eq 0) {
                    $before = $codeStr.Substring([Math]::Max(0, $j - 80), $j - [Math]::Max(0, $j - 80))
                    $before = $before -replace '\s+$', ''
                    if ($before -match '@(\w+)$') { $ownerKind = 'annotation'; $ownerName = $Matches[1] }
                    elseif ($before -match 'new\s+([\w\.]+)$') { $ownerKind = 'constructor'; $ownerName = ($Matches[1] -split '\.')[-1] }
                    elseif ($before -match '\.(\w+)$') { $ownerKind = 'method'; $ownerName = $Matches[1] }
                    elseif ($before -match '(\w+)$') { $ownerKind = 'call'; $ownerName = $Matches[1] }
                    break
                }
                $depth--
            }
            elseif ($ch -eq '[') { if ($depth -gt 0) { $depth-- } }
            elseif ($ch -eq ';' -or $ch -eq '{' -or $ch -eq '}') { if ($depth -eq 0) { break } }
            $j--
        }

        # Prefixo da sentenca: distingue atribuicao, return, case, lambda, concatenacao.
        $k = $pos - 1
        $stop = 0
        while ($k -ge 0) {
            $ch = $codeStr[$k]
            if ($ch -eq ';' -or $ch -eq '{' -or $ch -eq '}') { $stop = $k + 1; break }
            $k--
        }
        $stmt = ($codeStr.Substring($stop, $pos - $stop) -replace '\s+', ' ').Trim()
        if ($stmt.Length -gt 120) { $stmt = $stmt.Substring($stmt.Length - 120) }

        # Sufixo: pega o literal usado como RECEPTOR -> "x".equals(y)
        $endPos = $pos + 1
        $sufLen = [Math]::Min(60, $codeStr.Length - $endPos)
        $suffix = ''
        if ($sufLen -gt 0) { $suffix = ($codeStr.Substring($endPos, $sufLen) -replace '\s+', ' ').Trim() }

        $line = 1 + ([regex]::Matches($codeStr.Substring(0, $pos), "`n")).Count

        [void]$records.Add([pscustomobject]@{
            File = $f.FullName.Substring($Root.Length + 1); Line = $line; Value = $lit.Value
            Block = $lit.Block; OwnerKind = $ownerKind; OwnerName = $ownerName
            Stmt = $stmt; Next = $suffix
        })
    }
}

$records | Export-Csv -Path (Join-Path $OutDir 'literals.csv') -NoTypeInformation -Encoding UTF8

# ─── 3. Classificacao ─────────────────────────────────────────────────────────
# Cadeia de prioridades: a PRIMEIRA regra que casar vence. A ordem importa - lambda e
# receptor vem antes do dono da chamada, senao `put(() -> "x", v)` seria creditado ao put.
function Get-Reason($x) {
    $stmt = $x.Stmt; $next = $x.Next; $kind = $x.OwnerKind; $name = $x.OwnerName; $val = $x.Value
    $file = Split-Path $x.File -Leaf
    $isExc = $file -match '(Error|Exception)\.java$'

    if ($stmt -match '\(\s*\)\s*->\s*$') { return @('Nome de campo JSON (CcpJsonFieldName)', 'lambda  () -> "x"') }
    if ($stmt -match '->\s*$')           { return @('String solta', 'corpo de lambda') }

    if ($next -match '^\.\s*(\w+)\s*\(') {
        $m = $Matches[1]
        if ($m -match '^(equals|equalsIgnoreCase|contentEquals)$') { return @('Comparacao de valor', "`"literal`".$m(x)") }
        return @('Manipulacao / formatacao de texto', "`"literal`".$m(...)")
    }

    if ($kind -eq 'annotation') {
        switch -Regex ($name) {
            '^SuppressWarnings$' { return @('Diretiva de compilador', "@SuppressWarnings(`"$val`")") }
            '^(Operation|ApiResponse|ApiResponses|Schema|Tag|Parameter|Content|ExampleObject)$' { return @('Documentacao de API (OpenAPI)', "@$name") }
            '^(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping|PathVariable|RequestParam|RequestHeader|RequestBody|Value|Qualifier)$' { return @('Roteamento HTTP (Spring)', "@$name") }
            default { return @('Metadado do framework CCP', "@$name") }
        }
    }

    if ($isExc -and ($name -eq 'super' -or $kind -eq 'none' -or $name -match 'Error|Exception')) { return @('Mensagem de erro / validacao', "classe de excecao ($file)") }
    if ($kind -eq 'constructor' -and $name -match 'Error|Exception') { return @('Mensagem de erro / validacao', "new $name(...)") }
    if ($name -eq 'super') { return @('Mensagem de erro / validacao', 'super(...)') }

    if ($kind -eq 'constructor') {
        if ($name -match '^(CcpFieldName|CcpJsonFieldName)$') { return @('Nome de campo JSON (CcpJsonFieldName)', 'new CcpFieldName("x")') }
        if ($name -match '^(String|StringBuilder|CcpStringDecorator|CcpTextDecorator|CcpEmailDecorator)$') { return @('Manipulacao / formatacao de texto', "new $name(...)") }
        return @('String solta', "new $name(...)")
    }

    if ($kind -eq 'method' -or $kind -eq 'call') {
        switch -Regex ($name) {
            '^(replace|replaceAll|replaceFirst|split|matches|join|format|concat|substring|indexOf|trim|append|insert|joining|compile)$' { return @('Manipulacao / formatacao de texto', ".$name(...)") }
            '^(equals|equalsIgnoreCase|contains|startsWith|endsWith|contentEquals)$' { return @('Comparacao de valor', ".$name(...)") }
            '^(put|putProperty|putOperator|putAll|getAsString|getOrDefault|putIfNotContains|addToItem|getValueFromPath)$' { return @('Nome de campo JSON (CcpJsonFieldName)', ".$name(...)") }
            '^(forName|getDeclaredMethod|getDeclaredField|getMethod|getField|getResource|getResourceAsStream)$' { return @('Reflexao / carga por nome', ".$name(...)") }
            '^(getenv|getProperty|setProperty|elasticsearch_address|elasticsearch_secret|getTimeZone|SHA1|SHA256|SHA512|MD5)$' { return @('Configuracao / ambiente', ".$name(...)") }
            '^(setHeader|Content_Type|User_Agent|getHeader|addUrlPatterns|addResourceHandler|addResourceLocations|executeHttpRequest|executeMultiPartHttpRequest|verifyStatus|getHttpError|getHttpHandler)$' { return @('Infraestrutura HTTP', ".$name(...)") }
            '^(println|print|printf)$' { return @('Log / saida de console', ".$name(...)") }
            default { return @('String solta', ".$name(...)") }
        }
    }

    if ($stmt -match 'default\s*$')             { return @('Metadado do framework CCP', 'default de atributo de anotacao') }
    if ($stmt -match 'static\s+final\s+String') { return @('Constante nomeada', 'static final String') }
    if ($val -eq '' -and ($stmt -match '\+\s*$' -or $next -match '^\+')) { return @('Coercao para String ("" + x)', '"" + valor') }
    if ($stmt -match '\+\s*$' -or $next -match '^\+') { return @('Concatenacao (montagem de texto)', 'trecho concatenado') }
    if ($stmt -match 'return\s*$') { return @('String solta', 'return literal') }
    if ($stmt -match 'case\s*$')   { return @('Comparacao de valor', 'rotulo de switch') }
    if ($stmt -match ',\s*$')      { return @('String solta', 'item de lista de argumentos') }
    if ($stmt -match '=\s*$')      { return @('String solta', 'atribuicao a variavel local') }
    return @('String solta', 'sem contexto identificado')
}

$out = foreach ($x in $records) {
    $res = Get-Reason $x
    $cc = 'outro'
    if ($x.File -match '^ccp_') { $cc = 'ccp' } elseif ($x.File -match '^jn_') { $cc = 'jn' } elseif ($x.File -match '^jb_') { $cc = 'jb' } elseif ($x.File -match '^vis_') { $cc = 'vis' }
    [pscustomobject]@{ File = $x.File; Line = $x.Line; Value = $x.Value; Reason = $res[0]; Sub = $res[1]; CC = $cc }
}
$out | Export-Csv -Path (Join-Path $OutDir 'final.csv') -NoTypeInformation -Encoding UTF8

# ─── 4. Relatorio ─────────────────────────────────────────────────────────────
$total = $out.Count
"ARQUIVOS VARRIDOS: $($files.Count)   COM LITERAL: $(($out | Select-Object -ExpandProperty File -Unique).Count)   LITERAIS: $total"
""
"##### POR RAZAO DE EXISTIR #####"
$out | Group-Object Reason | Sort-Object Count -Descending | ForEach-Object {
    "{0,5}  {1,5}%  {2}" -f $_.Count, [math]::Round(100*$_.Count/$total,1), $_.Name
}
""
"##### SUBCATEGORIAS (top $($Top*2)) #####"
$out | Group-Object Reason, Sub | Sort-Object Count -Descending | Select-Object -First ($Top*2) | ForEach-Object {
    "{0,5}  {1}" -f $_.Count, $_.Name
}
""
"##### POR CENTRO DE CUSTO #####"
$out | Group-Object CC | Sort-Object Count -Descending | ForEach-Object { "{0,5}  {1}" -f $_.Count, $_.Name }
""
"##### TOP $Top ARQUIVOS #####"
$out | Group-Object File | Sort-Object Count -Descending | Select-Object -First $Top | ForEach-Object { "{0,5}  {1}" -f $_.Count, (Split-Path $_.Name -Leaf) }
""
"CSVs em: $OutDir"
