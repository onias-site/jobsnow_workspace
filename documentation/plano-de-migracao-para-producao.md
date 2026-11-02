# Plano de migração dos dados para a produção

Plano escrito em 2026-11-01. Os números foram lidos do Elasticsearch local (7.4, `localhost:9200`) nessa data. **Nenhum passo foi executado ou ensaiado ainda.**

**Objetivo:** subir a produção vazia, gravar as sementes e copiar só os dados reais, gerados por carga, sem levar dados de teste.

**Destino previsto:** Elastic Cloud Hosted, região de São Paulo, na versão 9.x. A suíte já foi rodada no 9.5.5.

**Decisões aplicadas:**

| Tema | Decisão |
|---|---|
| `vis_skill` | Levar só as 1.349 skills de `synonyms.json`. `LINUX EMBARCADO` e `PICK BY LIGHT` não vão, nem qualquer estatística ligada a elas. |
| `vis_recruiter` | Levar tudo, menos os 10 e-mails de `recrutadora.com.br`. |
| Decisões de hierarquia | Levar as 22 linhas reais, depois da conferência da fase 3, porque elas não foram aplicadas em `vis_skill`. |
| `jn_versionable` e `jn_disposable_record` | Não migrar. Em produção, as duas nascem só com o que o setup e os novos usos gravarem. |
| Sementes | Não copiar. O setup grava as sementes do código atual. |

## O que será migrado

A produção terminará com **861.124 registros** em 9 índices.

| # | Índice | Registros | Filtro |
|---|---|---:|---|
| 1 | `vis_telegram_position` | 204.855 | Nenhum; 21 registros são editados na fase 6 |
| 2 | `vis_statis_skill_line_chart` | 278.179 | Excluir `skill = LINUX EMBARCADO` (12) |
| 3 | `vis_statis_skill_pie_chart` | 8.592 | Nenhum; o `total` não muda |
| 4 | `jn_grouper` | 323.504 | Os valores de `parentName` da tabela abaixo |
| 5 | `vis_skill` | 1.349 | Excluir `LINUX EMBARCADO` e `PICK BY LIGHT` |
| 6 | `vis_recruiter` | 44.623 | Excluir `domain = recrutadora.com.br` |
| 7 | `vis_skill_fix_hierarchy_fulfiled` | 9 | `email` entre os 2 hashes da fase 3 |
| 8 | `vis_skill_fix_hierarchy_item_approved` | 6 | Os 6 itens da fase 3 |
| 9 | `vis_skill_fix_hierarchy_item_rejected` | 7 | Os 7 itens da fase 3 |

Valores de `parentName` em `jn_grouper`:

| `parentName` | Registros | Como chega à produção |
|---|---:|---|
| `vis_statis_skill_line_chart` | 278.179 | Cópia, sem os 12 grupos com `parentJson.skill = LINUX EMBARCADO` |
| `vis_statis_skill` | 31.960 | Cópia, sem os 9 grupos com `parentJson.skill = LINUX EMBARCADO` |
| `vis_statis_skill_pie_chart` | 8.592 | Cópia; 12 grupos são editados na fase 6 |
| `vis_virtual_recruiter_domain_initials_grouper` | 4.390 | Cópia; 1 grupo é editado na fase 6 |
| `vis_virtual_skill_initials_grouper` | 383 | **Não copiar:** a semente grava os grupos das 1.349 skills |

`parentJson` não é indexado, então os filtros por `parentJson.skill` precisam ser feitos no script, durante a leitura.

## O que fica de fora

| Dados | Motivo |
|---|---|
| Índices legados (`recruiters`, `old_recruiters`, `profissionais2` e os demais) | Fora do escopo. Sem eles o setup falha; a fase 4 resolve isso. |
| `js_login_*`, `jn_login_email` e envios de mensagem | Não há como separar uso real de teste, porque os e-mails estão em hash. As contas serão criadas de novo. |
| `vis_resume`, `vis_viewed_resume`, `vis_recruiter_resumes`, `js_contact_us` e tabelas pendentes | Dados de teste. |
| `jn_email_suppressed` e `jn_email_temporarily_blocked` | Registros falsos de teste. A lista real vem do SendGrid na fase 8. |
| `jn_disposable_record` | As 110.706 cópias das vagas estão vencidas e não seriam expurgadas. O restante é teste ou uso local. |
| `jn_versionable` | Só é lido para `vis_resume` e `vis_viewed_resume`, que não serão migrados. Levar tudo traria histórico de testes para o e-mail aos recrutadores. |
| `vis_skill_approved`, `vis_skill_rejected`, `vis_skill_reviewed` e `vis_skill_synonym` | Fora da lista. Consequência: `LINUX EMBARCADO`, `PICK BY LIGHT`, `KIPREV`, `JAB` e `CERENSA` poderão ser sugeridas de novo, porque a decisão fica no ambiente local. |
| 12 linhas de gráfico, 21 grupos e 4 referências em grupos de iniciais ligados às 2 skills aprovadas | Decisão de não levar nada dessas skills. `PICK BY LIGHT` não aparece em nenhuma vaga nem gráfico; todo o impacto vem de `LINUX EMBARCADO`. |

## Fases

### Fase 1: preparar o destino

1. Crie o cluster de produção e guarde o endereço e a credencial fora do repositório.
2. Monte um JSON de `application_properties` só para a migração, com `elasticsearch.address` e `elasticsearch.secret` da produção.
3. Confirme que o cluster está vazio.

### Fase 2: congelar a origem

1. Não rode a suíte, os roteiros, as APIs locais nem a carga do Telegram durante a extração. A cobertura do meio-dia também roda a suíte, então execute fora desse horário.
2. Faça um snapshot do 7.4 como cópia de segurança.
3. Reconte os índices da tabela de migração. Se algum número mudou, descubra o motivo antes de seguir.

### Fase 3: conferir as decisões de hierarquia

Confira estas linhas à mão. A separação entre real e teste foi feita por indício: os pedidos reais têm os termos em maiúsculas e não contêm `TESTE`.

Hashes de `email` em `vis_skill_fix_hierarchy_fulfiled`:

- `16911ce3b8bca2ebc4a7190231f140094834c419` (8 registros)
- `4f3b6ee8a84e4bdab624a23973679f7c836c7854` (1 registro)

Itens aprovados e reprovados:

| Tabela | `parent` | `skill` | `type` |
|---|---|---|---|
| `item_approved` | `NOSQLDATABASE` | `MEMCACHE` | `add` |
| `item_approved` | `NOSQLDATABASE` | `DATASTORE` | `remove` |
| `item_approved` | `SQLDATABASE` | `LINQ` | `remove` |
| `item_approved` | `JAVA SERVER` | `JERSEY` | `add` |
| `item_approved` | `ORMJAVA` | `ORACLE` | `add` |
| `item_approved` | `ORMJAVA` | `JDBC` | `add` |
| `item_rejected` | `SQLDATABASE` | `ELASTICSEARCH` | `add` |
| `item_rejected` | `CACHE` | `ELASTICSEARCH` | `add` |
| `item_rejected` | `ORMJAVA` | `SPRING` | `add` |
| `item_rejected` | `ORMJAVA` | `MYSQL` | `add` |
| `item_rejected` | `AJAX` | `EXTJS` | `remove` |
| `item_rejected` | `SQLDATABASE` | `JPA` | `remove` |
| `item_rejected` | `SQLDATABASE` | `HIBERNATE` | `remove` |

Migrar essas linhas apenas guarda as decisões. Aplicá-las a `vis_skill` é outro trabalho, fora deste plano.

### Fase 4: criar os índices e gravar as sementes

**Bloqueio:** a semente de `VisEntityRecruiter` lê `recruiters` e `old_recruiters`. Sem esses índices o setup aborta, e as 2 assinaturas de `jn_write_event_subscribers` não são gravadas. Copiar os índices legados só para isso gravaria dezenas de milhares de registros que a fase 5 substituiria, e levaria cerca de 18 minutos ou mais.

**Solução proposta, sem mudar código:** criar os dois índices vazios. A semente lê zero recrutadores e ainda grava as assinaturas. Esse caminho precisa ser provado no ensaio.

1. Crie `recruiters` e `old_recruiters` vazios na produção.
2. Em um terminal com as propriedades da fase 1, confira o endereço e rode `executaCcpCreateEntities.bat`, sem argumentos.
3. Confira `c:\logs\<centro de custo>\mappingJnEntitiesErrors.json` e `insertResults.json`, em `jn`, `js`, `vis` e `jb`.
4. Apague `recruiters` e `old_recruiters` da produção.

O setup apaga e recria os índices. Só `vis_telegram_position` mantém seus registros.

### Fase 5: copiar os dados

Use um script que leia o 7.4 por scroll e envie à produção por `_bulk`, com a ação `index` e o mesmo `_id` da origem.

**Por que não usar snapshot nem reindex remoto:** o snapshot não filtra registros, e um snapshot do 7.4 não restaura direto no 9.x. O reindex remoto exigiria que o cluster na nuvem alcançasse a máquina local.

1. Copie os índices 1 a 6 e depois os índices 7 a 9, nessa ordem.
2. Use `index`, não `create`: as sementes de `vis_skill` precisam ser substituídas pelos registros com ranking.
3. Não copie o `parentName` `vis_virtual_skill_initials_grouper`. Na origem, 3 desses grupos têm ids das 2 skills excluídas e um grupo (`PT`) só existe por causa delas; a semente já grava os grupos corretos.
4. Grave o `_source` sem alterações; as edições ficam para a fase 6.
5. Trate cada item do retorno do `_bulk`: falha parcial não derruba a chamada.
6. Registre quantos documentos foram enviados por índice.

### Fase 6: limpar o que sobrou

**Vagas com `LINUX EMBARCADO`.** Sem esta edição, o termo volta aos gráficos no próximo `VisBusinessRecalculateSkillStatistics`, porque ele recalcula tudo a partir de `vis_telegram_position`.

As 21 vagas têm outras skills, então nenhuma some, e os totais das outras skills e da pizza não mudam.

1. Localize as 21 vagas com `{"wildcard": {"skill": "*LINUX EMBARCADO*"}}`.
2. Tire `LINUX EMBARCADO` do campo `skill`, mantendo o separador `_` entre as demais.
3. Tire de `statisSkillLineChart` o id que pertence aos 12 registros excluídos de `vis_statis_skill_line_chart`.
4. Mantenha o `_id` da vaga: os grupos das outras skills apontam para ele.

**Consequência aceita:** o `_id` dessas 21 vagas deixa de corresponder à chave primária. Nenhum código lê vaga por id. Se a mesma vaga for carregada de novo, entra como outro registro.

**Grupos da pizza.** Em `jn_grouper`, nos 12 grupos com `parentName = vis_statis_skill_pie_chart` que têm `LINUX EMBARCADO` em `child`:

1. Tire de `child` o texto `{"skill":"LINUX EMBARCADO","total":...}`.
2. Diminua `childCount` em 1.

**Grupo de domínios.**

1. No `jn_grouper`, abra o documento `12623423b6e99a2f45d052daa02da12987882a2d`, o grupo `REC`.
2. Tire `recrutadora.com.br` de `child`.
3. Mude `childCount` de 36 para 35.

Os domínios `tmtestes.com.br`, `auditeste.com.br`, `conteste.com.br` e `fortestecnologia.com.br` são empresas reais e ficam.

**Ranking de `vis_skill`.** Fica sem as posições 806 e 1.351 até a próxima carga, que recalcula o ranking. Nenhuma edição é necessária.

### Fase 7: ajustar as sementes para a produção

| Registro | Ajuste |
|---|---|
| `jn_email_parameters_to_send`, modelo `VisNotifyRecruiterAboutResumes` | `frontendUrl` e `visApiUrl` nascem com `localhost`. Troque pelos endereços reais antes do primeiro e-mail. |
| `jn_email_parameters_to_send`, modelo `JnNotifyUserAboutLoginToken` | Confira `accessLink`, `telegramGroupLink` e `botAddress`. O token é enviado em todo login novo. |
| `jb_bot_allowed_user` | Confira os `chatId` dos operadores. A semente traz só `751717896`. |
| `jn_instant_messenger_parameters_to_send` | Todas as sementes apontam para o chat `751717896`. Confira se o suporte continua nesse chat. |

### Fase 8: validar e ligar

Confira as contagens:

| Índice | Esperado |
|---|---:|
| `vis_telegram_position` | 204.855 |
| `vis_statis_skill_line_chart` | 278.179 |
| `vis_statis_skill_pie_chart` | 8.592 |
| `jn_grouper` | 323.504 |
| `vis_skill` | 1.349 |
| `vis_recruiter` | 44.623 |
| `vis_skill_fix_hierarchy_fulfiled` | 9 |
| `vis_skill_fix_hierarchy_item_approved` | 6 |
| `vis_skill_fix_hierarchy_item_rejected` | 7 |
| `jn_write_event_subscribers` | 3 |
| `jn_session_validator` | 1 |
| `jn_system_message` | 222 |
| `jn_bot_command` | 8 |

Confirme que as 2 skills sumiram:

| Conferência | Esperado |
|---|---:|
| `vis_skill` com `LINUX EMBARCADO` ou `PICK BY LIGHT` | 0 |
| `vis_statis_skill_line_chart` com `skill = LINUX EMBARCADO` | 0 |
| `vis_telegram_position` com `*LINUX EMBARCADO*` em `skill` | 0 |
| Varredura de `jn_grouper` por `LINUX EMBARCADO` em `child` e `parentJson` | 0 |

Depois, nesta ordem:

1. Publique as APIs. Elas precisam subir depois dos dados, porque as entidades ficam em cache por 1 hora.
2. Teste a tela de grupos de vagas do Telegram, com um filtro de mês e região conhecido.
3. Teste a busca de habilidades (`/skills/fromText`) com uma skill do arquivo. `LINUX EMBARCADO` não deve ser reconhecida.
4. Teste a busca de empresas.
5. Crie uma conta nova, faça login e salve um currículo.
6. Registre o bot, seguindo `ligar-bot-de-producao.md`.
7. Crie `urlEmailSuppressionKey` e rode `JnBusinessLoadEmailSuppressions` com `startTimeInSeconds = 1`.
8. Agende `VisBusinessDailyScheduledProcess` só depois do passo 7. Enviar antes pode atingir endereços suprimidos.

## Ensaio obrigatório

Antes da produção, execute as fases 4 a 8 em um Elasticsearch 9.5.5 vazio. A instalação de `C:\elasticsearch-9.5.5` tem uma cópia dos dados, então use uma pasta de dados nova ou outra instalação, para não misturar com a cópia.

| O ensaio precisa provar | Por quê |
|---|---|
| O setup termina com os dois índices legados vazios | Nunca foi rodado assim; o que se sabe é que ele falha sem esses índices. |
| As contagens batem | Prova o filtro de cada índice. |
| `VisBusinessRecalculateSkillStatistics` não traz `LINUX EMBARCADO` de volta | Prova a edição das 21 vagas. Rode depois de conferir as contagens. |
| A tela de estatísticas, a busca de skills e a de empresas funcionam | Prova os grupos do `jn_grouper`. |
| `_source` do 7.4 é aceito pelos mapeamentos do 9.x | Os índices usam `dynamic: strict`. |
| O script aguenta o volume | São 860.741 documentos copiados. Meça o tempo e ajuste o tamanho do lote. |

## Dependências fora dos dados

Estes itens impedem o sistema de funcionar em produção, mas não bloqueiam a cópia dos dados:

- API publicada com HTTPS.
- Cache de produção: criar o Memorystore for Valkey (cluster mode disabled) e informar `memorystore.host` e `memorystore.port`; o `CcpGcpMemoryStore` nunca foi testado contra um Valkey real.
- Pub/Sub e consumidor publicados.
- Repositório de snapshot `gcs` para o backup diário.

## Riscos

| Risco | Prevenção |
|---|---|
| Rodar o setup apontando para o banco errado | Conferir o endereço antes da fase 4 e usar as propriedades só naquele terminal. |
| Rodar `CcpCreateEntities` depois de migrar | **Nunca rode com `vis` em produção:** ele recria `vis_recruiter`, `vis_skill` e os gráficos. |
| Suíte de testes apontando para a produção | Usar as propriedades apenas no terminal da migração. |
| Extrair enquanto a suíte grava | Seguir a fase 2. |
| `LINUX EMBARCADO` voltar a ser reconhecida | Uma sugestão nova aprovada, ou o termo incluído em `vis_skill`, faz a skill valer de novo na próxima carga. |
| Recrutador de teste legado receber e-mail | Ficam `teste@onias.com`, `teste2@onias.com`, `teste@t1.com`, `teste@t2.com` e `teste@xxx2.com`, além das contas do próprio projeto (`ccpjobsnow@gmail.com`, `ccpjobsnow1@gmail.com`, `devs.jobsnow@gmail.com` e `onias@ccpjobsnow.com`). Isso segue a decisão de levar tudo, menos os 10. |

## Como voltar atrás

A migração não altera a origem. Até publicar as APIs, apague os índices da produção e repita a partir da fase 4. Depois que houver usuários reais, não repita a fase 4: ela apagaria os dados deles.
