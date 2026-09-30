# Contar Classes Java por Centro de Custo

Conta a quantidade de arquivos `.java` em cada centro de custo do projeto jobsnow (CCP, JN, JB, VIS), exibindo o subtotal por módulo e o total geral por centro de custo.

## Argumento esperado

Nenhum. A skill opera sobre a estrutura fixa do projeto em `C:\eclipse-workspaces\ccp`.

## Passos

1. Listar todos os diretórios filhos imediatos de `C:\eclipse-workspaces\ccp`.
2. Agrupar os diretórios pelos prefixos de centro de custo: `ccp_*`, `jn_*`, `jb_*`, `vis_*`.
3. Para cada centro de custo, percorrer recursivamente cada módulo e contar os arquivos `.java`.
4. Exibir o resultado em formato de tabela com:
   - Subtotal por módulo (indentado sob o centro de custo)
   - Total geral por centro de custo
   - Total geral de todos os centros de custo ao final
5. Usar o seguinte comando PowerShell para coletar os dados:

```powershell
$root = "C:\eclipse-workspaces\ccp"
$centros = @("ccp", "jn", "jb", "vis")

foreach ($cc in $centros) {
    $dirs = Get-ChildItem -Path $root -Directory | Where-Object { $_.Name -like "$cc`_*" }
    $total = 0
    $detalhes = @()
    foreach ($dir in $dirs) {
        $count = (Get-ChildItem -Path $dir.FullName -Filter "*.java" -Recurse -File).Count
        $total += $count
        $detalhes += "  $($dir.Name): $count"
    }
    Write-Output "=== $($cc.ToUpper()) === TOTAL: $total"
    $detalhes | ForEach-Object { Write-Output $_ }
    Write-Output ""
}
```

6. Apresentar os resultados em uma tabela Markdown resumida com as colunas: Centro de Custo | Classes Java | Descrição.

## Restrições

- Contar apenas arquivos com extensão `.java` (não `.class`, não outros tipos).
- Ignorar o diretório `jn_frontend_calistrato-react` no total do JN (não contém Java).
- Os quatro centros de custo ativos são: CCP, JN, JB, VIS — não incluir outros prefixos.
- A descrição de cada centro de custo a usar na tabela final:
  - CCP → Framework (DI, decorators, utilitários, integrações)
  - JN → Infraestrutura central do JobsNow
  - JB → BackOffice / suporte
  - VIS → Visualização de currículos
