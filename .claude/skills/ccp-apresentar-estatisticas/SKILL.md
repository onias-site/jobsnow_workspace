---
name: ccp-apresentar-estatisticas
description: Relatório por centro de custo (com.ccp, com.jn, com.jb, com.vis) com as classes e os métodos públicos do código de produção, o índice de métodos por classe (IMC), os testes JUnit (@Test) de cada pacote, o índice de testes por classe (ITC) e a fatia de cada pacote no total de métodos, de testes e de classes, mais a linha agregadora do módulo de testes, os @Ignore e os testes do front end à parte. Só lê o código-fonte, não compila nem roda nada. Use quando perguntarem "quantos testes temos", "tamanho da suíte", "quantos @Test", "quantos métodos públicos", "quantas classes por pacote", "proporção de testes por classe", ou antes/depois de uma campanha de testes para comparar.
---

# Classes, métodos públicos e testes por centro de custo

Funde as antigas `ccp-contar-testes` e `ccp-contar-metodos-publicos` (fusão pedida pelo usuário em 2026-10-12).

## Passos

1. Rodar o script (leva poucos segundos):

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-apresentar-estatisticas/scripts/contar.sh"
   ```

   A saída tem uma linha por dado, separada por TAB:
   - `pacote <nome> <classes> <métodos públicos> <testes>`, uma por pacote de 2º nível;
   - `agregador ccp_rest-api-tests_jobsnow <classes> 0 0`, o módulo de testes;
   - `ignorados`, `classesComIgnore`;
   - `moduloComTestes <nome> <testes>`, uma por módulo Java que tem testes;
   - `frontend <casos> <arquivos>`, os `it(...)`/`test(...)` dos `*.spec.*`/`*.test.*` do front end.

2. Responder com o total de testes e o total de classes em destaque na primeira frase e uma tabela com as colunas,
   nesta ordem:

   **Pacote** | **Classes** | **Métodos públicos** | **IMC** | **Testes** | **ITC** | **% do total de métodos** | **% do total de testes** | **% do total de classes**

   - Uma linha por `pacote`, na ordem do script, e depois a linha do `agregador`, com Métodos públicos, IMC, Testes,
     ITC, % do total de métodos e % do total de testes zerados (os testes dele já estão distribuídos nos pacotes).
   - **IMC** (índice métodos por classe) = Métodos públicos ÷ Classes da linha, com duas casas decimais e vírgula
     (ex.: `3,73`).
   - **ITC** (índice de testes por classe; até 2026-10-12 se chamava ICT) = Testes ÷ Classes da linha, com duas casas decimais e vírgula (ex.: `6,36`).
   - As porcentagens têm duas casas decimais e vírgula (ex.: `66,06%`), arredondadas. O total de classes inclui as
     classes do agregador.
   - Fechar com a linha **Total**: soma das colunas, IMC = total de métodos públicos ÷ total de classes, ITC = total
     de testes ÷ total de classes, e **100%** nas três
     colunas de porcentagem. Se uma soma de porcentagens não der 100% por causa do arredondamento, dizer isso em uma
     linha abaixo da tabela.
   - Citar em uma linha os `@Ignore` (quantos e em quais classes) e, se houver, os testes do front end, deixando claro
     que ficam fora da suíte Java (rodam com `npm test`/Jest). Se aparecer mais de um módulo Java com testes,
     acrescentar a divisão por módulo.

## Como conta

- **Classes**: arquivos `.java` com uma declaração de tipo (classe, interface, enum, anotação ou record). Pela regra
  de um tipo por arquivo, é o número de tipos; os arquivos vazios propositais não contam.
  - Produção: `src/main/java` de todos os módulos, menos os dependency chooser (`dependency-chooser`,
    `dependency_chooser` e o diretório truncado terminado em `_dependency`), que só fazem o wiring da DI, e menos o
    módulo de testes.
  - Agregador: os tipos de `ccp_rest-api-tests_jobsnow/src/test/java` (classes de teste e auxiliares).
- **Métodos públicos**: linhas que declaram método `public` (com `(` na assinatura), sem campos, sem declarações de
  classe/interface/enum e sem atribuições de campo com `(` no inicializador. A regex diferencia maiúsculas: a versão
  antiga, em PowerShell, ignorava maiúsculas e descartava os métodos que devolvem `Class<?>` (17 a menos em
  2026-10-12).
- **Testes**: linhas que começam com `@Test` (sozinho, com parâmetros ou com o método na mesma linha), atribuídas ao
  pacote de 2º nível do arquivo de teste. Menção em comentário e `@TestXxx` não contam. `@Ignore` é contado à parte e
  **não** é descontado: o teste existe, só não roda.
- `documentation/` fica de fora: guarda módulos aposentados só como fonte, que não compilam nem rodam.
- É contagem estática: testes parametrizados contam uma vez por `@Test`. Para saber quantos **rodaram** e passaram,
  use os relatórios do Surefire de uma execução.

## Restrições

- Somente leitura: não compilar, não rodar testes, não alterar arquivos.
