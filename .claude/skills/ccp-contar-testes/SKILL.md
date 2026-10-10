---
name: ccp-contar-testes
description: Conta quantos testes unitários/de integração (@Test do JUnit) a suíte completa tem, por pacote (com.ccp, com.jn, com.jb, com.vis), com o número de classes e os @Ignore, mais os testes do front end à parte. Só lê o código-fonte, não compila nem roda nada. Use quando perguntarem "quantos testes temos", "tamanho da suíte", "quantos testes unitários", "quantos @Test", ou antes/depois de uma campanha de testes para comparar.
---

# Contar os testes da suíte

A suíte Java fica toda em `ccp_rest-api-tests_jobsnow` (os demais módulos não têm `src/test/java`). O script
varre todos os módulos mesmo assim, para que um teste novo fora dele também entre na conta.

## Passos

1. Rodar o script (leva poucos segundos):

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-contar-testes/scripts/contar-testes.sh"
   ```

   A saída tem uma linha por dado, separada por TAB:
   - `total`, `classes`, `ignorados`, `classesComIgnore`;
   - `pacote <nome> <testes> <classes>`, uma por pacote de 2º nível;
   - `modulo <nome> <testes>`, uma por módulo com testes;
   - `frontend <casos> <arquivos>`, os `it(...)`/`test(...)` dos `*.spec.*`/`*.test.*` do front end.

2. Responder com o total em destaque na primeira frase e uma tabela por pacote (**Pacote** | **Testes** |
   **Classes**), fechando com a linha de total. Citar em uma linha os `@Ignore` (quantos e em quais classes) e,
   se houver, os testes do front end, deixando claro que ficam fora da suíte Java (rodam com `npm test`/Jest).
   Se aparecer mais de um módulo Java com testes, acrescentar a divisão por módulo.

## Como conta

- Um teste é uma linha que começa com `@Test`: sozinho, com parâmetros (`@Test(timeout = ...)`) ou com o
  método na mesma linha (`@Test public void x() {...}`). Menção em comentário e `@TestXxx` não contam.
- `@Ignore` é contado à parte e **não** é descontado do total: o teste existe, só não roda.
- `documentation/` fica de fora: guarda módulos aposentados só como fonte (ex.: `text-extractor_apache-tika`),
  que não compilam nem rodam.
- É contagem estática: testes parametrizados ou gerados em tempo de execução contam uma vez por `@Test`.
  Para saber quantos **rodaram** e passaram, use os relatórios do Surefire de uma execução, nunca esta contagem.

## Restrições

- Somente leitura: não compilar, não rodar testes, não alterar arquivos.
