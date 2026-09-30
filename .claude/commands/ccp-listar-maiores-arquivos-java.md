# Listar Maiores Arquivos Java

Lista os maiores arquivos `.java` do workspace inteiro (todos os módulos/projetos sob `C:\eclipse-workspaces\ccp`) em dois rankings: os 20 com maior número de **bytes** e os 20 com maior número de **linhas**. Serve para localizar candidatos a refatoração — classes que cresceram demais e concentram responsabilidade.

## Argumento esperado

Opcional. `$ARGUMENTS` representa a quantidade de itens de cada ranking (top N). Se vazio ou inválido, usar **20**.

## Passos

1. Determinar o `N` a partir de `$ARGUMENTS` (padrão 20).
2. Varrer recursivamente `C:\eclipse-workspaces\ccp` atrás de arquivos `.java`, ignorando diretórios que não são código-fonte do projeto (ver Restrições).
3. Para cada arquivo, coletar: módulo (primeiro segmento do caminho relativo à raiz), nome do arquivo, tamanho em bytes, quantidade de linhas e a densidade `BytesPorLinha` (bytes ÷ linhas, arredondado em 1 casa decimal).
4. Executar o comando PowerShell abaixo para coletar os dados (ajustar `$top` conforme o passo 1):

```powershell
$root = "C:\eclipse-workspaces\ccp"
$top = 20
$excluded = '\\(\.metadata|\.git|target|bin|node_modules|\.settings)\\'
$files = Get-ChildItem -Path $root -Filter *.java -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch $excluded }
$stats = foreach ($f in $files) {
    $relativo = $f.FullName.Substring($root.Length + 1)
    $modulo = $relativo.Split('\')[0]
    $linhas = [System.IO.File]::ReadAllLines($f.FullName).Count
    if ($linhas -eq 0) { $densidade = 0 } else { $densidade = [math]::Round($f.Length / $linhas, 1) }
    [pscustomobject]@{ Modulo = $modulo; Arquivo = $f.Name; Bytes = $f.Length; Linhas = $linhas; BytesPorLinha = $densidade; Caminho = $relativo }
}
Write-Output "TOTAL DE ARQUIVOS ANALISADOS: $($stats.Count)"
Write-Output "=== TOP $top POR BYTES ==="
$stats | Sort-Object Bytes -Descending | Select-Object -First $top Modulo, Arquivo, Bytes, Linhas, BytesPorLinha | Format-Table -AutoSize | Out-String -Width 200
Write-Output "=== TOP $top POR LINHAS ==="
$stats | Sort-Object Linhas -Descending | Select-Object -First $top Modulo, Arquivo, Linhas, Bytes, BytesPorLinha | Format-Table -AutoSize | Out-String -Width 200
```

5. Apresentar **duas tabelas Markdown** separadas, cada uma com as colunas: `#` | Arquivo | Módulo | Linhas | Bytes | Bytes/Linha — a primeira ordenada por bytes, a segunda por linhas.
6. Informar o total de arquivos `.java` analisados e comentar brevemente as diferenças relevantes entre os dois rankings, usando a coluna Bytes/Linha: valor alto indica linhas longas (expressões extensas, concatenações, assinaturas grandes); valor baixo indica muitas linhas curtas (declarações, imports, blocos rasos).

## Restrições

- Considerar **todos** os módulos do workspace, não apenas um centro de custo.
- Excluir sempre: `.metadata` (histórico local do Eclipse, cheio de cópias antigas de `.java` que poluem o ranking), `target`, `bin`, `.git`, `node_modules` e `.settings`.
- Contar linhas com `[System.IO.File]::ReadAllLines()` — é bem mais rápido que `Get-Content | Measure-Object -Line` em centenas de arquivos.
- Apenas leitura: a skill não altera nenhum arquivo.
