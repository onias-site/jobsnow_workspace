---
name: ccp-relatorio-de-cobertura
description: Relatório de porcentagem de cobertura de código do workspace — roda a suíte de ccp_rest-api-tests_jobsnow com o agente JaCoCo (o mesmo motor do EclEmma) e gera uma página HTML expansível no formato da view Coverage do Eclipse (workspace > projeto > src/main/java > pacote > arquivo, com Coverage, Covered/Missed/Total Instructions) mais um TSV por arquivo. Use quando pedirem "cobertura de código", "coverage", "porcentagem de cobertura", "quanto do código os testes cobrem", "relatório do EclEmma/JaCoCo", "quais classes não têm teste", ou para comparar a cobertura antes e depois de uma mudança.
---

# Relatório de cobertura de código

Mede quanto do bytecode de `com.ccp`, `com.jn`, `com.jb` e `com.vis` é executado pelos testes, e
apresenta no mesmo formato da view **Coverage** do EclEmma: uma árvore expansível
workspace › módulo › `src/main/java` › pacote › arquivo, com barra, porcentagem e as contagens de
instruções cobertas, perdidas e totais.

## Como funciona

1. `mvn -o test -fn -pl ccp_rest-api-tests_jobsnow` com
   `-DargLine=-javaagent:jacocoagent.jar=destfile=jacoco.exec,includes=com.ccp.*:com.jn.*:com.jb.*:com.vis.*`.
   O `-fn` faz o Maven seguir mesmo com testes falhando — teste vermelho também gera cobertura.
2. `CoverageReport.java` (motor `org.jacoco.core`) lê os `.exec` e analisa, para **cada** módulo do
   workspace, o bytecode que de fato rodou: o jar do módulo no `~/.m2` (é o que a JVM dos testes
   carrega), a cópia do `target/classes` de onde a API rodou, e só em último caso o `target/classes`.
   Conta só as classes cujo fonte está no `src/main/java` do próprio módulo, porque os jars Spring
   Boot trazem as dependências (inclusive `ccp_commons`) em `BOOT-INF/lib`.
   **O projeto de testes (`ccp_rest-api-tests_jobsnow`) fica fora do relatório e da porcentagem
   geral**, por decisão do usuário em 2026-10-02: o `src/main` dele é código de apoio aos testes
   (~8.900 instruções sempre a 0 %), não código de produção, e só puxaria o número para baixo.
3. Saídas em `-OutDir` (padrão `%TEMP%\ccp-coverage`):
   - `coverage-report.html` — página única, sem dependência externa, tema claro/escuro, linhas
     clicáveis para expandir;
   - `coverage.tsv` — `project  package  file  coverage  covered  missed  total`, uma linha por
     arquivo, boa para ordenar/filtrar ou comparar duas rodadas;
   - no console, a árvore até o nível de pasta de fonte.

Os jars (agente, core e ASM) vêm do `~/.m2` — JaCoCo 0.8.12 e ASM 9.7 já estão lá.

## Parâmetros

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `-Root` | `C:\eclipse-workspaces\ccp` | raiz do workspace |
| `-Module` | `ccp_rest-api-tests_jobsnow` | módulo cujos testes rodam |
| `-Test` | vazio (suíte inteira) | filtro do Surefire, ex. `'com.jn.services.login.**'` ou `'SavePassword,ExecuteLogin'` |
| `-OutDir` | `%TEMP%\ccp-coverage` | onde ficam exec, html e tsv — **não pode ter espaço** (quebra o `-javaagent`) |
| `-SkipRun` | desligado | não roda testes; só regera o relatório a partir do `jacoco.exec` existente (e do `jacoco-api.exec`, se houver) |
| `-NoApi` | desligado | não sobe a API jn; os testes REST só passam se ela já estiver no ar |
| `-IncludeTestModule` | desligado | inclui no relatório o próprio `ccp_rest-api-tests_jobsnow`, que por padrão fica de fora |

## Passos

1. Se houve mudança em módulo de negócio, instalar antes (o módulo de testes consome o jar do
   `.m2`, e o relatório compara com o `target/classes` — os dois precisam ser do mesmo build):

   ```powershell
   mvn -o -q install -DskipTests -pl <modulos alterados>
   ```

2. Rodar o script **em segundo plano** (a suíte inteira leva vários minutos):

   ```powershell
   & "<raiz>\.claude\skills\ccp-relatorio-de-cobertura\scripts\coverage-report.ps1"
   ```

3. Publicar o `coverage-report.html` como Artifact (é o formato que o usuário aprovou) e dar o
   link; mencionar também o caminho local do HTML e do TSV.

4. No texto da resposta, trazer:
   - **quantos testes foram executados** para gerar aqueles números, logo antes da tabela, no
     formato "N testes executados: P passaram, F falhas, E erros, S pulados" (é a linha `TESTS:`
     do console e a linha "Tests run" do topo do HTML; o script grava em `tests-run.txt`, que o
     `-SkipRun` reaproveita). Pedido do usuário em 2026-10-02: a cobertura nunca é apresentada sem
     essa informação, porque uma rodada com muitos testes quebrados mede menos código;
   - a tabela de cobertura por módulo, com as colunas **# | Módulo | Cobertura | Cobertas |
     Perdidas | Total** (instruções), uma linha por módulo, **terminando sempre com a linha "Total
     geral"** em negrito, que soma cobertas, perdidas e total de todos os módulos da tabela e traz
     a porcentagem dessa soma (é a última linha do console, `TOTAL`). A coluna **#** é um contador
     que começa em 1 na primeira linha e sobe de 1 em 1; a linha "Total geral" não recebe número
     (fica vazia nessa coluna). Pedidos do usuário em 2026-10-02: a tabela nunca sai sem o total
     geral nem sem a coluna #. Se a tabela agrupar módulos numa linha só (ex. "adaptadores 0 %"),
     essa linha recebe um único número, e o total geral continua sendo a soma de todos eles;
     exemplo do formato:

     | # | Módulo | Cobertura | Cobertas | Perdidas | Total |
     |---|---|---|---|---|---|
     | 1 | ccp_json_gson | 81,8 % | 426 | 95 | 521 |
     | 2 | jn_business_jobsnow | 74,3 % | 23.671 | 8.185 | 31.856 |
     | … | … | | | | |
     | | **Total geral** | **64,0 %** | **102.197** | **57.487** | **159.684** |
   - os módulos/pacotes com 0 % que têm volume relevante de instruções — são o achado;
   - quantos testes falharam na rodada (o script imprime as linhas `<<< FAILURE/ERROR`), porque
     teste quebrado no meio do fluxo derruba a cobertura do que vem depois.

5. Para comparar antes/depois, guardar o `coverage.tsv` da primeira rodada com outro nome e
   comparar por `project+package+file`, nunca só pelo total.

## Restrições e armadilhas

- **A API jn é medida junto, por padrão.** Se a porta 8080 estiver livre, o script sobe
  `JnRestApiSpringStarter` (classpath via `dependency:build-classpath`, como na memória "Subir a
  API jn sem Eclipse") com um agente em modo `tcpserver` na porta 6300, roda a suíte, coleta os
  dados com `AgentDump.java` (o processo é derrubado à força e não gravaria nada ao sair), para a
  API e entrega os dois `.exec` juntos ao `CoverageReport`. Se a 8080 já estiver ocupada (API no
  Eclipse), os testes usam essa API mas o código dela não é medido: o script avisa. `-NoApi`
  desliga tudo isso. A API do vis não é iniciada. A API sobe com
  `-Dspring.devtools.restart.enabled=false`: com o DevTools ligado, uma recompilação do Eclipse
  reinicia a API no meio da rodada e os testes REST daquele instante tomam "connection refused"
  (foi o que derrubou 3 testes do `PasswordLoginScreen` em 2026-10-02).
- **Com o Eclipse aberto, a suíte pode nem começar.** Em 2026-10-02 o Surefire morreu na varredura
  com `ClassNotFoundException` de uma classe de teste que o Eclipse estava regravando em
  `target/test-classes`. O script detecta o `.exec` vazio e para com erro em vez de publicar um
  relatório falso; basta rodar de novo.
- **Sem a API no ar, ~62 testes REST quebram com connection refused** (`com.jn.rest.api.*`; o
  script avisa). A cobertura muda pouco, porque o código da API roda em outro processo, mas a
  contagem de vermelhos fica inflada — dizer isso ao relatar. Para subir a API, ver a memória
  "Subir a API jn sem Eclipse".

## Baseline

2026-10-02, suíte inteira com a API jn medida: 2343 testes, 1 falha + 4 erros, **64,0 %** de
159.684 instruções sem o projeto de testes (60,6 % de 168.574 com ele). jn_business 74,3 % · ccp_commons 72,4 % · jb_business 67,2 % ·
vis_business 29,9 % (o maior bloco descoberto: 14.280 instruções).
- **Nunca analisar o `target/classes`.** O JaCoCo casa classe por checksum do bytecode, e o
  Eclipse regrava o `target/classes` com o compilador dele, sem a tecelagem do AspectJ. Em
  2026-10-02 isso aconteceu no meio da rodada, e 3/4 do código sumiu do relatório. Pelo mesmo
  motivo, a primeira medição do dia (60,5 % de 149 mil instruções) tinha perdido em silêncio os
  adaptadores `ccp_db-*`, `ccp_http`, `ccp_json` etc. Hoje o gerador lê os jars do `.m2` e avisa
  quantas classes não bateram ("WARNING: N classes ran from bytecode different..."). Se aparecer
  esse aviso, o módulo citado provavelmente não foi instalado depois da última mudança: rode
  `mvn -o install -DskipTests` nele e repita.
- **Classes tecidas pelo AspectJ** (toString gerado, aspectos de null) entram com as instruções
  do aspecto; é o mesmo número que o EclEmma mostra dentro do Eclipse.
- **A suíte inteira envia mensagens reais ao Telegram** (`JnServiceLoginTemplateDeTestes` injeta o
  messenger real, por decisão do usuário) e usa o Elasticsearch local. Avisar antes de rodar.
- **Com o Eclipse aberto**, ele pode segurar lock em `target/` e recompilar em paralelo; se o
  relatório vier com módulos inteiros zerados, rodar `mvn -o clean install -DskipTests` e repetir.
- Interfaces, anotações e enums só com constantes aparecem com 0 instruções (0,0 % de 0) — não é
  falta de teste.
