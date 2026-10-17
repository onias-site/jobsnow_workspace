# Carga concorrente sobre os currículos: comparação entre implementações de CcpMensageriaSender

Começado em 2026-10-15. Objetivo: medir, com N clientes simultâneos, os endpoints do currículo (GET, inativar, reativar,
excluir, reinserir), o `POST /skills/fromText` e os do login, e comparar o comportamento conforme a implementação de
`CcpMensageriaSender` usada pelas APIs jn (8080) e vis (8081).

## Rodadas feitas

| # | Pasta | CcpMensageriaSender | Níveis | Requisições | Erros | Parou em |
|---|---|---|---|--:|---|---|
| 1 | `1-sincrono` | `syncMensageriaListener` | 10, 50, 100, 250 | 7559 | 550 só no 250 (12,38%) | 250 |
| 2 | `2-assincrono-10-50-100` | `asyncMensageriaListener` | 10, 50, 100 | 3099 | 194 no 100 (10%) | 100 |
| 3 | `3-assincrono-250` | `asyncMensageriaListener` | 250 (541 candidatos) | 4932 | 96 (1,95%) | — |

Cada pasta tem `summary.md` (nível x endpoint: bytes de entrada e saída, requisições em voo, p50/p95, heap da JVM),
`summary.csv`, `progress.log` e, nas assíncronas, `settles.csv` (espera até o ES mostrar o que cada fase gravou). Os
`requests.csv` (uma linha por requisição) e os backups ficaram só em `C:\logs\carga-concorrente\<pasta da rodada>`.

## Tempo mediano (p50, ms)

| Endpoint | 100 síncrono | 100 assíncrono | 250 síncrono | 250 assíncrono |
|---|--:|--:|--:|--:|
| HEAD login | 1396 | 1609 | 1651 | 3341 |
| POST login | 14901 | 19034 | 36216 | 31242 |
| GET currículo | 1051 | 973 | 2199 | 2131 |
| inativar / reativar | 32429 | 3185 | 37458 | 9028 |
| excluir | 20587 | 11628 | 28508 | 6696 |
| salvar (reinserir) | 26826 | 4243 | 42326 | 7001 |
| fromText | 1813 | 119 (133 recusas) | 1975 | 2921 |
| logout | 1320 | 641 | 3556 | 5136 |
| Heap máx. do vis (MB) | 1526 | 1401 | 1724 | 2246 |

## O que se aprendeu

- **Servidor web é Jetty** (não Tomcat). Os erros de conexão são rajadas de conexões novas maiores que a fila de aceite:
  `ECONNREFUSED`/`ECONNRESET`. Acontecem no começo de uma fase quando as conexões ficaram ociosas (o Jetty as fecha) e
  N clientes reconectam juntos. Não houve 5xx, timeout do Elasticsearch (0 rejeições nos thread pools) nem OutOfMemory.
- **Síncrono**: o trabalho da fila roda dentro da requisição; as escritas degradam muito (salvar com 27 s de mediana
  com 100 clientes).
- **Assíncrono**: as escritas respondem de 3 a 6 vezes mais rápido, mas o trabalho continua em threads de fundo (uma
  `new Thread` por mensagem, sem limite) e chega ao ES de 10 a 50 s depois; o heap do vis sobe mais.
- **A API responde antes de gravar**: logo depois do login o GET dá 401 `invalidSession` e ~2 s depois dá 200. O
  script espera o ES mostrar a gravação antes da fase seguinte e mede essa espera (tabela "Espera da escrita
  assíncrona" do `summary.md`).
- **Reativar com 250 clientes** ficou lento (p95 81 s) e não convergiu em 180 s; 26 tarefas de fundo falharam com
  `CcpErrorFlowDisturb ... has been moved from 'vis_inactive_resume' to 'vis_resume'`. Causa não identificada. A gêmea
  `vis_inactive_resume` **já tem** `JnAsyncWriterEntity` (conferido imprimindo `VisEntityResume.ENTITY.getTwinEntity()`).
- **Login é o gargalo nos dois modos** (~31 s de mediana com 250); hipótese não medida: BCrypt custo 12, CPU.
- Nenhum currículo se perdeu: o total ficou em 4141 nas três rodadas. A reinserção grava sempre na entidade principal,
  então os inativos do ciclo voltam ativos; o reset abaixo desfaz isso.

## Correção feita no caminho

`AsyncMensageriaListener` passou a chamar `CcpMensageriaReceiver.executeProcessAndRecordOutcome` (método abstrato
novo; o `JnMensageriaReceiver` grava sucesso ou erro em `jn_async_task`). Antes a falha de uma tarefa de fundo ia só
para o stderr. Teste: `ReceiverOutcomeTest.aFailureInTheLocalAsynchronousMessagingIsRecorded`.

## Como continuar com uma nova implementação de CcpMensageriaSender

1. **Onde trocar**: `JnRestApiSpringStarter.java` (linha 92) e `VisRestApiSpringStarter.java` (linha 93), no ternário
   `localEnvironment ? CcpLocalInstances.asyncMensageriaListener : new CcpGcpPubSubMensageriaSender()`. As
   implementações locais ficam em `ccp_mocking_jobsnow`, `com.ccp.local.testings.implementations` (`CcpLocalInstances`,
   `SyncMensageriaListener`, `AsyncMensageriaListener`). Uma nova implementação deve chamar
   `receiver.executeProcessAndRecordOutcome(topic, json)` para gravar o resultado em `jn_async_task`.
2. **Instalar e reiniciar**: `mvn -o install -DskipTests -pl <módulos alterados>`, depois
   `mvn -q -o compile -pl jn_rest-api_spring_jobsnow_dependency-chooser,vis_rest-api_spring_jobsnow_dependency-chooser`
   e subir as APIs fora do Eclipse (ver a memória "Subir a API jn sem Eclipse"; o classpath de cada uma vem de
   `mvn dependency:build-classpath`).
3. **Rodar a carga** (em `documentation/roteiros-de-teste/automacao`), sempre com o reset antes:

   ```bash
   # níveis 10, 50 e 100
   RESET_FROM="C:\\logs\\carga-concorrente\\2026-10-15-completa" node 10-carga-concorrente-curriculos.mjs "C:\\logs\\carga-concorrente\\<data>-<nome>"
   # só 250, com o mesmo número de candidatos das rodadas anteriores, sem parar por erro
   STOP_ERROR_RATE=1 RESET_FROM="C:\\logs\\carga-concorrente\\2026-10-15-completa" node 10-carga-concorrente-curriculos.mjs "C:\\logs\\carga-concorrente\\<data>-<nome>-250" 250 541
   ```

   O reset devolve cada currículo à situação ativo/inativo do backup de `2026-10-15-completa` (3964 ativos, 177
   inativos), pela própria API; **não apague essa pasta**. `RESET_ONLY=1` faz só o reset.
4. **Comparar**: copiar `summary.md`, `summary.csv`, `settles.csv` e `progress.log` para uma pasta nova aqui
   (`4-<nome>`) e acrescentar colunas nas tabelas acima.

Pré-requisitos: ES em 9200, candidatos em `C:\logs\carga-profissionais2`, senha da carga `Carga@2026Curriculo`, tokens
de login lidos de `c:\logs\email`.

## Ideias que ficaram em aberto

- Investigar a lentidão do reativar com 250 clientes e as 26 falhas de fundo da gêmea.
- Rodar com a fila de aceite do Jetty maior, ou com o cliente abrindo as conexões aos poucos, para separar a recusa de
  conexão da lentidão do back end.
- Medir o custo do BCrypt no login.
