---
name: mapear-strings-literais
description: Varre todos os arquivos .java do workspace e produz um relatório que agrupa as strings literais por "razão de existir" (documentação OpenAPI, mensagem de erro, @SuppressWarnings, nome de campo JSON, concatenação, string solta, etc.), com contadores por categoria, por centro de custo e por arquivo. Use quando pedirem para "mapear as strings literais", "relatório de strings", "onde estão as strings soltas", "quantas strings literais existem" ou ao procurar candidatos a virar enum de field name / constante.
---

# Mapear strings literais por razão de existir

Produz um inventário classificado de todas as strings literais do código Java de produção.
Serve para achar candidatos a refatoração (chave literal que deveria ser enum de field name,
mensagem duplicada, texto de documentação misturado ao código) e para medir a evolução
desses números entre uma refatoração e outra.

## Argumento esperado

Nenhum obrigatório. O script aceita três parâmetros opcionais:

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `-Root` | `C:\eclipse-workspaces\ccp` | raiz do workspace a varrer |
| `-OutDir` | `$env:TEMP\map-literals` | onde gravar os CSVs |
| `-Top` | `12` | tamanho dos rankings de arquivos e subcategorias |

## Passos

1. Executar o script que acompanha a skill:

   ```powershell
   & "<raiz>\.claude\skills\mapear-strings-literais\scripts\map-literals.ps1"
   ```

   Ele imprime o relatório agregado em stdout e grava dois CSVs no `-OutDir`:
   - `literals.csv` — um registro por literal, com o contexto sintático cru (prefixo da
     sentença, sufixo, e quem é o "dono" da chamada). Use para reclassificar sem varrer tudo de novo.
   - `final.csv` — o mesmo já classificado: `File, Line, Value, Reason, Sub, CC`.

2. Apresentar o resultado ao usuário em tabelas markdown, nesta ordem:
   - **contadores por razão de existir**, com quantidade e percentual, do maior para o menor;
   - **detalhamento das 3 ou 4 maiores categorias** por subcategoria;
   - **por centro de custo** (ccp / jn / jb / vis);
   - **top arquivos**.

3. Sempre declarar as ressalvas do método (ver abaixo). Elas não são decoração: já
   levaram a uma contagem inflada em ~2,5× numa categoria.

4. Se o usuário pedir para agir sobre alguma categoria (trocar literais por enum, por
   exemplo), **abrir cada ocorrência e conferir antes de alterar**. Nunca agir em lote a
   partir do número do relatório.

## Como a classificação funciona

Tokenizador próprio, não regex solta sobre o arquivo. Máquina de estados que ignora
comentários de linha e de bloco, literais de char e escapes, e entende text blocks (`"""`).
Cada caractere consumido vira espaço num buffer paralelo de mesmo comprimento, preservando
quebras de linha — assim a varredura para trás nunca tropeça em parêntese que esteja dentro
de comentário ou de string, e o índice continua servindo para calcular a linha.

Para cada literal são capturados três sinais:

- **dono da chamada** — varredura para trás até o `(` não-balanceado mais próximo, e quem o
  precede: `@Anotacao`, `new Tipo`, `.metodo` ou chamada simples;
- **prefixo da sentença** — distingue atribuição, `return`, `case`, lambda, concatenação;
- **sufixo** — pega o literal usado como receptor, caso de `"x".equals(y)`.

A classificação é uma cadeia de prioridades em que a primeira regra que casa vence. **A ordem
importa**: lambda e receptor são testados antes do dono da chamada, senão
`put(() -> "x", v)` seria creditado ao `put` em vez de ser reconhecido como criação de
`CcpJsonFieldName`.

## Categorias produzidas

`Documentacao de API (OpenAPI)` · `Mensagem de erro / validacao` · `String solta` ·
`Concatenacao (montagem de texto)` · `Diretiva de compilador` ·
`Manipulacao / formatacao de texto` · `Roteamento HTTP (Spring)` · `Infraestrutura HTTP` ·
`Nome de campo JSON (CcpJsonFieldName)` · `Comparacao de valor` ·
`Metadado do framework CCP` · `Coercao para String ("" + x)` · `Configuracao / ambiente` ·
`Reflexao / carga por nome` · `Constante nomeada`

## Restrições

- **O projeto de testes fica fora.** `ccp_rest-api-tests_jobsnow` é excluído, junto com
  `target/`, `node_modules/` e `bin/`. Alterar isso muda a base de comparação entre execuções.
- **A classificação é heurística sintática, não análise semântica com resolução de tipos.**
  Três limites conhecidos, que devem ser repetidos ao usuário toda vez:
  - *Indireção derrota o classificador.* Literal que passa por variável local antes do uso
    real cai em "String solta". É o caso dos códigos HTTP (`"200"`, `"400"`) que só depois
    viram `@ApiResponse`.
  - *`Concatenacao` é sobre forma, não propósito.* São pedaços montados com `+`; parte deles
    é mensagem de erro que não está dentro de classe de exceção.
  - *`Nome de campo JSON` superestima.* `.put(...)` e afins também recebem literal como
    **valor**, não só como chave. Numa auditoria real dos 54 casos apontados, **32 eram
    falsos positivos**: valor de header, URL default, template de mensagem, script painless,
    e sobretudo assinaturas em que a chave já é enum e o literal é o `defaultValue`
    (`getOrDefault(Campo.x, () -> "0")`, `getValueFromPath(T defaultValue, CcpJsonFieldName... paths)`).
- **Não gravar arquivo Java com `Set-Content`/`Out-File` a partir deste fluxo.** Os fontes
  têm acentuação e a leitura/regravação corrompe os javadocs (`Nó` vira `NÃ³`). Para editar
  código use a ferramenta de edição, que preserva a codificação.
- Não é preciso `jq` — não está instalado nesta máquina. Tudo é PowerShell + `ConvertFrom-Json`
  quando necessário.

## Baseline

Execução de 2026-09-16, após a troca de 22 chaves literais por enums de field name:

| | |
|---|---|
| Arquivos varridos | 515 (206 com literal) |
| Literais | 1.707 |
| Maior categoria | Documentação OpenAPI — 439 (25,7%) |
| String solta | 255 (14,9%) |
| Nome de campo JSON | 32 — hoje **quase todos falsos positivos**, os verdadeiros já foram convertidos |
| Por centro de custo | ccp 835 · jn 451 · vis 366 · jb 55 |

A execução anterior, antes daquela refatoração, dava 1.729 literais e 54 em "Nome de campo
JSON". A diferença de exatamente 22 nos dois números confirma que o relatório é estável e
serve para medir progresso.
