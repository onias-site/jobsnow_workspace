# Listar Repositórios por Quantidade de Commits

Lista todos os repositórios de uma organização (ou usuário) do GitHub ordenados em ordem decrescente pela quantidade de commits da branch padrão, exibindo também branch, visibilidade e o total geral.

## Argumento esperado

O nome da organização (ou usuário) do GitHub. Se nenhum argumento for informado, usar `onias-site` como padrão.

Exemplos:
- `/listar-repos-por-commits` → usa `onias-site`
- `/listar-repos-por-commits minha-org`

## Passos

1. Verificar se o `gh` CLI está autenticado com `gh auth status`. Se não estiver, orientar o usuário a rodar `! gh auth login` e parar.
2. Gerar o script abaixo em um arquivo temporário no scratchpad da sessão, substituindo `<ORG>` pela organização informada, e executá-lo:

```powershell
$org = "<ORG>"
$repos = gh repo list $org --limit 200 --json name,defaultBranchRef,isPrivate | ConvertFrom-Json
$results = @()
foreach ($r in $repos) {
    $branch = $r.defaultBranchRef.name
    $count = 0
    try {
        $out = gh api -i "repos/$org/$($r.name)/commits?sha=$branch&per_page=1" 2>$null
        $text = ($out -join "`n")
        $m = [regex]::Match($text, '<[^>]*[?&]page=(\d+)>;\s*rel="last"')
        if ($m.Success) {
            $count = [int]$m.Groups[1].Value
        } else {
            $bodyStart = $text.IndexOf("`n[")
            if ($bodyStart -ge 0) {
                $body = $text.Substring($bodyStart) | ConvertFrom-Json
                $count = ($body | Measure-Object).Count
            }
        }
    } catch { $count = -1 }
    $results += [pscustomobject]@{ Repo = $r.name; Branch = $branch; Private = $r.isPrivate; Commits = $count }
}
$results | Sort-Object Commits -Descending | Format-Table -AutoSize
"TOTAL REPOS: $($results.Count)  TOTAL COMMITS: $(($results | Measure-Object -Property Commits -Sum).Sum)"
```

3. Apresentar o resultado em uma tabela Markdown com as colunas: **#** | **Repositório** | **Branch** | **Commits**. Marcar repositórios privados com 🔒 ao lado do nome.
4. Informar o total de repositórios e o total de commits somados.
5. Destacar observações relevantes quando existirem: repositórios cuja branch padrão não é `main`, repositórios privados e a concentração de commits nos primeiros colocados (percentual sobre o total).

## Restrições

- A contagem usa o header `Link` (`rel="last"`) da API do GitHub com `per_page=1` — é o número de commits alcançáveis **apenas pela branch padrão**. Sempre explicitar isso ao usuário: commits que existam somente em outras branches não entram no total.
- Quando a resposta não trouxer header `Link` (repositório com um único commit ou vazio), contar as entradas retornadas no corpo JSON.
- Repositórios que falharem na consulta recebem `-1` e devem ser sinalizados como erro na saída, não omitidos.
- Não usar o endpoint `/contributors` como alternativa — ele é limitado a 500 contribuidores e pode divergir da contagem real.
- Não clonar os repositórios para contar commits localmente; a operação deve ser feita apenas via API.
