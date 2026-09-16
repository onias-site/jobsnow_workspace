# Contar Tasks Pendentes por Centro de Custo

Conta ocorrências dos marcadores de task pendente (`FIXME`, `TODO`, `ATTENTION`, `LATER`, `DOUBT`) em arquivos `.java` de cada centro de custo do projeto jobsnow (CCP, JN, JB, VIS), exibindo o subtotal por tipo de marcador e o total geral por centro de custo.

## Argumento esperado

Nenhum. A skill opera sobre a estrutura fixa do projeto em `C:\eclipse-workspaces\ccp`.

## Passos

1. Listar todos os diretórios filhos imediatos de `C:\eclipse-workspaces\ccp`.
2. Agrupar os diretórios pelos prefixos de centro de custo: `ccp_*`, `jn_*`, `jb_*`, `vis_*`.
3. Para cada centro de custo, ler o conteúdo de todos os arquivos `.java` recursivamente.
4. Contar as ocorrências de cada marcador: `FIXME`, `TODO`, `ATTENTION`, `LATER`, `DOUBT`.
5. Usar o seguinte comando PowerShell para coletar os dados:

```powershell
$root = "C:\eclipse-workspaces\ccp"
$centros = @("ccp", "jn", "jb", "vis")
$tags = @("FIXME", "TODO", "ATTENTION", "LATER", "DOUBT")
$grandTotal = 0

foreach ($cc in $centros) {
    $dirs = Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -like "$cc`_*" }
    $files = $dirs | ForEach-Object { Get-ChildItem -Path $_.FullName -Filter "*.java" -Recurse -File }

    Write-Output "=== $($cc.ToUpper()) ==="
    $ccTotal = 0
    foreach ($tag in $tags) {
        $count = 0
        foreach ($file in $files) {
            $lines = Get-Content $file.FullName -Encoding UTF8
            foreach ($line in $lines) {
                $trimmed = $line.Trim()
                # comentário de linha: // em qualquer posição antes do marcador
                $inSlashComment = $line -cmatch "//.*\b$tag\b"
                # comentário de bloco/Javadoc: linha começa com * (dentro de /* */ ou /** */)
                $inBlockComment = $trimmed -cmatch "^\*.*\b$tag\b"
                if ($inSlashComment -or $inBlockComment) {
                    $count++
                }
            }
        }
        $ccTotal += $count
        Write-Output "  $tag`: $count"
    }
    Write-Output "  TOTAL: $ccTotal"
    $grandTotal += $ccTotal
    Write-Output ""
}
Write-Output "=== GRAND TOTAL: $grandTotal ==="
```

6. Apresentar os resultados em uma tabela Markdown com as colunas: Centro de Custo | FIXME | TODO | ATTENTION | LATER | DOUBT | TOTAL.
7. Incluir uma linha de totais por tipo de marcador (soma das colunas).
8. Destacar o centro de custo com maior número de pendências como observação final.

## Restrições

- Contar apenas em arquivos `.java` — ignorar outros tipos.
- Os quatro centros de custo ativos são: CCP, JN, JB, VIS — não incluir outros prefixos.
- Uma task só é válida se o marcador estiver dentro de um comentário Java:
  - Comentário de linha (`//`): marcador em qualquer posição após `//` na mesma linha
  - Comentário de bloco/Javadoc (`/* */` / `/** */`): linha deve começar com `*`
- Usar word boundary `\b` para evitar falsos positivos de substrings (ex: `TODOS`, `MÉTODO`)
- A contagem é case-sensitive.
- Os marcadores aceitos são exatamente: `FIXME`, `TODO`, `ATTENTION`, `LATER`, `DOUBT`.
