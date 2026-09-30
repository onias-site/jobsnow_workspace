---
name: ccp-relatorio-de-testes
description: Relatório da suíte de testes do workspace — quantos testes existem, como estão distribuídos por pacote, quais o Surefire não alcança, quais estão desativados por comentário, e o resultado da última execução lido de target/surefire-reports (com os nomes dos testes que quebraram). Use quando pedirem "quantos testes eu tenho", "relatório de testes", "como está a suíte", "quais testes estão falhando", "o que quebrou depois da minha mudança", ou antes/depois de mexer em algo para comparar o antes e o depois.
---

# Relatório da suíte de testes

Responde duas perguntas diferentes que costumam ser confundidas:

- **quantos testes existem** — inventário estático do que o Surefire executaria;
- **o que aconteceu na última execução** — leitura dos `target/surefire-reports`.

A segunda pergunta só cobre o que foi rodado. Confundir as duas é como afirmar que a suíte está
verde depois de rodar 3% dela.

## Por que não é um `grep -c '@Test'`

Três motivos, todos já observados neste workspace:

- **`grep` conta `@Test` dentro de comentários.** Há 11 `//@Test` em
  `com/vis/rest/api/resume/validations/` — testes desativados à mão, que não aparecem como
  `skipped` em relatório nenhum e que um `grep` cru soma como se estivessem ativos.
- **o nome da classe decide se ela roda.** As classes BDD em português (`ResendLoginToken`,
  `SavePassword`, `AoEntrarNaTelaDoCadastroDeSenha`) não casam com `*Test` / `Test*` / `*Tests` /
  `*TestCase`. Elas só rodam porque o `pom.xml` lista os pacotes delas em `<includes>`. Um pacote
  BDD novo que ninguém adicione ao pom fica invisível: compila, não roda, e nada avisa.
- **classe de apoio não é teste.** Templates (`JnTemplateDeTestes`), fixtures e `VariaveisParaTeste`
  estão em `src/test` e são excluídos explicitamente.

O script lê os `<includes>`/`<excludes>` do próprio pom e reproduz a decisão do Surefire, em vez de
chutar por nome.

## Argumento esperado

Nenhum obrigatório.

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `-Root` | `C:\eclipse-workspaces\ccp` | raiz do workspace |
| `-Module` | `ccp_rest-api-tests_jobsnow` | módulo de testes (hoje é o único com `src/test`) |
| `-Package` | vazio | limita tudo a um pacote, ex. `com/jn/services/login` |
| `-Top` | 15 | quantos pacotes listar |
| `-AllPackages` | desligado | lista todos em vez do `-Top` |
| `-NoReports` | desligado | só o inventário, sem ler os surefire-reports |
| `-FailedNames` | vazio | grava os nomes dos testes que quebraram, para comparar depois |

## Passos

1. Executar o script:

   ```powershell
   & "<raiz>\.claude\skills\ccp-relatorio-de-testes\scripts\test-report.ps1"
   ```

2. Apresentar, nesta ordem:
   - **total de testes** e de classes — é a resposta à pergunta feita;
   - **órfãos** e **desativados por comentário**, se houver: são achados, não estatística. Um teste
     que ninguém roda é pior que um teste que falha, porque não aparece em relatório nenhum;
   - **distribuição por pacote**, que mostra onde a suíte é densa e onde é rala;
   - **última execução**, sempre dizendo **de quando** são os reports e **que fração** do
     inventário eles cobrem.

3. Ao relatar execução, **nunca afirmar "a suíte está verde"** se os reports cobrem só parte do
   inventário. Dizer qual pacote foi rodado e quantos dos N testes aquilo representa.

4. Se o usuário quer comparar antes/depois de uma mudança, rodar com `-FailedNames` **antes** e
   **depois** e comparar as duas listas:

   ```powershell
   Compare-Object (Get-Content antes.txt) (Get-Content depois.txt)
   ```

   Comparar **por nome**, nunca por contagem: nesta suíte já aconteceu de o total permanecer 16 e
   ainda assim a natureza de todas as falhas ter mudado.

## Como rodar os testes (para depois pedir o relatório)

```powershell
# um pacote (aceita ** para subpacotes)
mvn -o -pl ccp_rest-api-tests_jobsnow test -Dtest='com.jn.services.login.**'

# classes especificas: separar por virgula, nao por +
mvn -o -pl ccp_rest-api-tests_jobsnow test -Dtest='SavePassword,ExecuteLogin'

# suite inteira
mvn -o -pl ccp_rest-api-tests_jobsnow test
```

Antes disso, se houve mudança em módulo de negócio, instalar o módulo no `.m2` — o módulo de testes
consome o jar, não o fonte:

```powershell
mvn -o -q -pl jn_business_jobsnow install -DskipTests
```

## Restrições

- **Os reports são cumulativos e não são limpos entre execuções.** Rodar uma classe só deixa os
  XMLs antigos das outras no diretório, e o relatório os somaria como se fossem da mesma rodada. É
  por isso que o script informa a janela de horários dos arquivos: se ela for larga, os números
  vêm de execuções diferentes. Para leitura limpa, apagar `target\surefire-reports` antes de rodar.
- **É análise estática do fonte.** Não expande `@RunWith(Parameterized)` nem testes herdados de
  classe-mãe abstrata (hoje não há nenhum dos dois; o script avisa se aparecer uma abstrata com
  `@Test`).
- **Contagem de `@Test` despreza comentários**, e é por isso que ela difere de um `grep` cru — a
  diferença é reportada como "desativados por comentário".
- **Os testes compartilham o Elasticsearch local**, e várias entidades são descartáveis por hora
  (`CcpEntityExpurgableOptions.hourly`). O mesmo teste pode passar numa rodada e falhar na
  seguinte por causa de registro deixado pela anterior — já aconteceu com `ResendLoginToken`.
  Antes de tratar uma falha como regressão, repetir a execução.
- **`JnServiceLoginTemplateDeTestes` injeta o `CcpTelegramInstantMessenger` real**: rodar os testes
  de login envia mensagens de verdade ao bot de suporte. Não é acidente — é decisão registrada do
  usuário — mas convém avisar antes de rodar a suíte inteira.
- **A carga inicial das entidades (`CcpCreateEntities`) é destrutiva**: recria todos os índices de
  jn e jb. Só rodar com autorização explícita, e cuidado que ela precisa do diretório de trabalho
  em `ccp_rest-api-tests_jobsnow` (os caminhos dos scripts são relativos).

## Baseline

Execução de 2026-09-21, sem filtro:

| | |
|---|---|
| Arquivos `.java` em `src/test` | 252 |
| Classes de teste (as que o Surefire roda) | **158** |
| Métodos `@Test` | **1972** |
| dos quais `@Test(expected=...)` | 1168 |
| Desativados por comentário | 11 (em 2 classes de `com/vis/rest/api/resume/validations`) |
| `@Ignore` / `@RunWith` | 0 / 0 |
| Órfãos (têm `@Test`, o pom não alcança) | 0 |

Módulos com `src/test`: **só** `ccp_rest-api-tests_jobsnow`. Os outros 27 não têm teste nenhum.

Maiores pacotes: `com.ccp.decorators` 499 · `...entity.decorators.engine` 148 ·
`...db.query` 115 · `...validations.fields.annotations` 82 · `com.jn.entities` 74 ·
`...especifications.http` 68 · `com.jn.services.login` 59 · `com.jn.rest.api.login` 58.

Para referência histórica: 1832 `@Test` em 2026-09-16, 1972 em 2026-09-21. O pacote
`com.jn.services.login` fechou 59/59 em 2026-09-21, vindo de 25 erros; a suíte completa não foi
medida nessa data.
