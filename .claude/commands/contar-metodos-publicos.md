# Contar Métodos Públicos por Módulo

Conta a quantidade de declarações de métodos públicos em todos os arquivos `.java` do projeto jobsnow, agrupando o resultado por módulo e exibindo o total geral.

## Argumento esperado

Nenhum. A skill opera sobre a estrutura fixa do projeto em `C:\eclipse-workspaces\ccp`.

## Passos

1. Localizar todos os arquivos `.java` recursivamente em `C:\eclipse-workspaces\ccp`, excluindo os módulos `dependency_chooser`, `dependency-chooser` e `ccp_rest-api-tests_jobsnow`. Atenção: o diretório de `jn_mensageria-consumer_gcp-pubsub-push-spring_dependency` está truncado em `_dependency` (sem o sufixo `_chooser`), por isso o filtro também precisa cobrir esse formato.
2. Varrer cada arquivo linha a linha contando as linhas que declaram métodos públicos, usando o seguinte comando PowerShell:

```powershell
$files = Get-ChildItem "C:\eclipse-workspaces\ccp" -Recurse -Filter "*.java" |
    Where-Object { $_.FullName -notmatch "dependency.chooser|_dependency\\|ccp_rest-api-tests_jobsnow" }

$pattern = '^\s+(?:(?:@\w[\w.]*(?:\s*\([^)]*\))?\s+)|(?:(?:static|final|abstract|synchronized|native|default|strictfp)\s+))*public\s+(?:(?:static|final|abstract|synchronized|native|default|strictfp)\s+)*(?!class\b|interface\b|enum\b|@interface\b)\S'

$result = $files |
    Select-String -Pattern $pattern |
    Where-Object { $_.Line -match '\w\s*\(' } |
    Where-Object { $_.Line -notmatch '=\s*\S.*\(' }

$byModule = $result | Group-Object {
    $rel = $_.Path -replace [regex]::Escape("C:\eclipse-workspaces\ccp\"), ""
    ($rel -split "\\")[0]
} | Sort-Object Count -Descending

$byModule | ForEach-Object {
    Write-Output ("{0,-55} {1,5}" -f $_.Name, $_.Count)
}
Write-Output ("-" * 62)
Write-Output ("{0,-55} {1,5}" -f "TOTAL", ($byModule | Measure-Object Count -Sum).Sum)
```

3. Apresentar os resultados em uma tabela Markdown com as colunas: **Módulo** | **Métodos Públicos**.
4. Destacar o módulo com maior número de métodos e calcular sua porcentagem sobre o total.

## Restrições

- Contar apenas declarações de métodos (linhas com `(` na assinatura) — não contar campos públicos, declarações de classe, interface ou enum.
- Excluir os projetos dependency chooser (`dependency_chooser`, `dependency-chooser` e o diretório truncado terminado em `_dependency`) e `ccp_rest-api-tests_jobsnow` (módulo de testes). Os choosers apenas fazem o wiring das implementações concretas via DI, então sua superfície pública não representa código de negócio.
- Não contar atribuições de campo que contenham `(` no inicializador (filtro `=\s*\S.*\(`).
