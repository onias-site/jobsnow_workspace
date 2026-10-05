# Contar Classes Java por Centro de Custo

Conta a quantidade de arquivos `.java` em cada centro de custo do projeto jobsnow (CCP, JN, JB, VIS) e, numa linha à parte, no projeto de testes (`ccp_rest-api-tests_jobsnow`), exibindo o subtotal por módulo, o total por grupo e a porcentagem de cada grupo sobre o total geral.

## Argumento esperado

Nenhum. A skill opera sobre a estrutura fixa do projeto em `C:\eclipse-workspaces\ccp`.

## Passos

1. Listar todos os diretórios filhos imediatos de `C:\eclipse-workspaces\ccp`.
2. Agrupar os diretórios pelos prefixos de centro de custo: `ccp_*`, `jn_*`, `jb_*`, `vis_*`. O projeto de testes `ccp_rest-api-tests_jobsnow` **não** entra no CCP: forma um grupo próprio, "Testes".
3. Para cada grupo, percorrer recursivamente cada módulo e contar os arquivos `.java`.
4. Calcular a porcentagem de cada grupo sobre o total geral (soma dos cinco grupos, testes incluídos), com uma casa decimal.
5. Usar o seguinte comando PowerShell para coletar os dados:

```powershell
$root = "C:\eclipse-workspaces\ccp"
$testProject = "ccp_rest-api-tests_jobsnow"
$groups = [ordered]@{
    "ccp"    = { param($n) $n -like "ccp_*" -and $n -ne $testProject }
    "jn"     = { param($n) $n -like "jn_*" -and $n -ne "jn_frontend_calistrato-react" }
    "jb"     = { param($n) $n -like "jb_*" }
    "vis"    = { param($n) $n -like "vis_*" }
    "testes" = { param($n) $n -eq $testProject }
}

$allDirs = Get-ChildItem -Path $root -Directory
$results = [ordered]@{}
foreach ($group in $groups.Keys) {
    $filter = $groups[$group]
    $modules = [ordered]@{}
    foreach ($dir in ($allDirs | Where-Object { & $filter $_.Name })) {
        $modules[$dir.Name] = (Get-ChildItem -Path $dir.FullName -Filter "*.java" -Recurse -File).Count
    }
    $results[$group] = $modules
}

$grandTotal = 0
foreach ($modules in $results.Values) { foreach ($count in $modules.Values) { $grandTotal += $count } }

foreach ($group in $results.Keys) {
    $total = 0
    foreach ($count in $results[$group].Values) { $total += $count }
    $percent = if ($grandTotal -gt 0) { [math]::Round(100.0 * $total / $grandTotal, 1) } else { 0 }
    Write-Output "=== $($group.ToUpper()) === TOTAL: $total ($percent %)"
    foreach ($module in $results[$group].Keys) { Write-Output "  ${module}: $($results[$group][$module])" }
    Write-Output ""
}
Write-Output "=== TOTAL GERAL === $grandTotal"
```

6. Apresentar os resultados em uma tabela Markdown resumida com as colunas: **Centro de Custo | Classes Java | Porcentagem | Descrição**, uma linha por grupo na ordem CCP, JN, JB, VIS, Testes, terminando com a linha **Total** (100 %).
7. Abaixo da tabela, listar o subtotal por módulo de cada grupo.

## Restrições

- Contar apenas arquivos com extensão `.java` (não `.class`, não outros tipos).
- Ignorar o diretório `jn_frontend_calistrato-react` no total do JN (não contém Java).
- O projeto de testes `ccp_rest-api-tests_jobsnow` fica sempre numa linha própria ("Testes"), nunca somado ao CCP.
- Os grupos são: CCP, JN, JB, VIS e Testes. Não incluir outros prefixos.
- A porcentagem é sobre o total geral (os cinco grupos somados), com uma casa decimal; a linha Total mostra 100 %.
- A descrição de cada grupo a usar na tabela final:
  - CCP → Framework (DI, decorators, utilitários, integrações)
  - JN → Infraestrutura central do JobsNow
  - JB → BackOffice / suporte
  - VIS → Visualização de currículos
  - Testes → Projeto de testes (`ccp_rest-api-tests_jobsnow`), que cobre todos os centros de custo
