# Contar Tipos Java por Centro de Custo

Conta a quantidade de declarações de `class`, `interface`, `enum` e `annotation` em cada centro de custo do projeto jobsnow (CCP, JN, JB, VIS), exibindo o subtotal por módulo e o total geral por centro de custo.

## Argumento esperado

Nenhum. A skill opera sobre a estrutura fixa do projeto em `C:\eclipse-workspaces\ccp`.

## Passos

1. Listar todos os diretórios filhos imediatos de `C:\eclipse-workspaces\ccp`.
2. Agrupar os diretórios pelos prefixos de centro de custo: `ccp_*`, `jn_*`, `jb_*`, `vis_*`.
3. Para cada módulo, percorrer recursivamente todos os `.java` e contar ocorrências de cada tipo de declaração usando regex.
4. Exibir por módulo e acumular subtotal por centro de custo.
5. Usar o seguinte comando PowerShell para coletar os dados:

```powershell
$root = "C:\eclipse-workspaces\ccp"
$centros = @("ccp", "jn", "jb", "vis")

foreach ($cc in $centros) {
    $dirs = Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -like "$cc`_*" }
    Write-Output "=== $($cc.ToUpper()) ==="
    $ccClasses = 0; $ccInterfaces = 0; $ccEnums = 0; $ccAnnotations = 0
    foreach ($dir in $dirs) {
        $files = Get-ChildItem -Path $dir.FullName -Filter "*.java" -Recurse -File
        $classes = 0; $interfaces = 0; $enums = 0; $annotations = 0
        foreach ($file in $files) {
            $content = Get-Content $file.FullName -Raw
            $classes     += ([regex]::Matches($content, '\bclass\s+\w+')).Count
            $interfaces  += ([regex]::Matches($content, '(?<!@)\binterface\s+\w+')).Count
            $enums       += ([regex]::Matches($content, '\benum\s+\w+')).Count
            $annotations += ([regex]::Matches($content, '@interface\s+\w+')).Count
        }
        $ccClasses += $classes; $ccInterfaces += $interfaces; $ccEnums += $enums; $ccAnnotations += $annotations
        Write-Output "  $($dir.Name) | classes:$classes | interfaces:$interfaces | enums:$enums | annotations:$annotations"
    }
    Write-Output "  >> SUBTOTAL $($cc.ToUpper()) | classes:$ccClasses | interfaces:$ccInterfaces | enums:$ccEnums | annotations:$ccAnnotations"
    Write-Output ""
}
```

6. Apresentar os resultados em uma tabela Markdown resumida com as colunas: Centro de Custo | Classes | Interfaces | Enums | Annotations | Total.

## Restrições

- Contar declarações dentro dos arquivos `.java` (inclui inner classes/enums/interfaces).
- Os quatro centros de custo ativos são: CCP, JN, JB, VIS — não incluir outros prefixos.
- `annotation` é identificada por `@interface`; `interface` comum não deve contar `@interface`.
