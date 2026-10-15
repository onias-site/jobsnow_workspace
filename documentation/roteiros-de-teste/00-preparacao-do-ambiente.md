# Roteiros de teste — preparação do ambiente

Estes roteiros testam, à mão e de ponta a ponta, as duas funcionalidades da aba **Habilidades** da tela "Ver meu currículo":

| Arquivo | Funcionalidade | Onde fica na tela |
|---|---|---|
| [01-sugerir-habilidade.md](01-sugerir-habilidade.md) | Sugerir uma habilidade que o sistema deixou de listar (`VisEntitySkillPending`) (executado de verdade em 2026-10-08) | Link **"Deixamos de listar alguma habilidade?"** |
| [02-sugerir-ajuste-de-hierarquia.md](02-sugerir-ajuste-de-hierarquia.md) | Sugerir associar/desassociar habilidades de um conhecimento implícito (`VisEntitySkillFixHierarchyPending`) (executado de verdade em 2026-10-08) | Ícones ⊕ (`pi-plus-circle`) e 🗑 (`pi-trash`) no título de cada conhecimento implícito |
| [03-modal-de-login.md](03-modal-de-login.md) | Modal de login: primeiro acesso, senha, bloqueios, desbloqueio e reenvio pelo suporte (executado de verdade no navegador) | Abre sozinho quando uma ação exige login |
| [04-tela-do-curriculo.md](04-tela-do-curriculo.md) | Tela do currículo: preencher as 4 abas, salvar, carregar, inativar, reativar e excluir, LinkedIn compartilhado e agrupadores (desde 2026-10-15) | Menu **Como estou indo → Ver meu currículo** |
| [05-endpoints-do-curriculo-pela-tela.md](05-endpoints-do-curriculo-pela-tela.md) | Os quatro endpoints de `VisRestApiResume` (ler, salvar, inativar/reativar, excluir) a partir da tela, com 401, 404 e respostas sem dados da sessão (desde 2026-10-15) | Tela "Ver meu currículo" |

Cada roteiro é feito de **cenários**. Cada cenário tem: o que fazer na tela do candidato, o que fazer no Telegram como **operador do suporte**, e o que conferir (tela, e-mail, Telegram, Elasticsearch). Marque os `[ ]` à medida que avançar. Onde está escrito **⚠ Atenção**, o comportamento descrito é o atual do sistema e merece a sua avaliação — não é erro de quem testa.

Faça este arquivo **uma vez**, antes dos roteiros 01 e 02.

---

## 1. Os dois papéis

| Papel | Quem é | Por onde age |
|---|---|---|
| **Candidato** | você logado como `onias85@gmail.com` | navegador, `http://localhost:3000` |
| **Operador do suporte** | você no Telegram, no chat com o bot de suporte (chat id `751717896`) | aplicativo do Telegram |

As sugestões do candidato chegam ao operador **como uma mensagem do bot no Telegram** (ex.: `/reviewSkillSuggestion onias85@gmail.com PICK BY LIGHT`). Para o operador agir, basta **copiar essa mensagem e enviá-la de volta ao bot** — o bot responde com a sugestão e as opções.

---

## 2. Subir o que é preciso

| # | O quê | Como | Como saber que subiu |
|---|---|---|---|
| 2.1 | Elasticsearch local | o serviço de sempre | `http://localhost:9200` responde um JSON com `"cluster_name"` |
| 2.2 | API do **jn** (login) — porta 8080 | Eclipse: rodar `com.jn.rest.api.JnRestApiSpringStarter` | `http://localhost:8080/rota/inexistente` responde 404 |
| 2.3 | API do **vis** (habilidades) — porta 8081 | Eclipse: rodar `com.vis.rest.api.VisRestApiSpringStarter` | `http://localhost:8081/rota/inexistente` responde 404 |
| 2.4 | Leitor do bot de suporte (Telegram) | Eclipse: rodar `com.jb.instant.messenger.reader.JbInstantMessengerReaderStarter` do projeto `jb_instant-messenger-listener_jobsnow_dependency-chooser` (sem argumentos = bot `support`, lendo para sempre) | mande `/chatId` ao bot no Telegram: ele responde `751717896` |
| 2.5 | Front end | em `jn_frontend_calistrato-react`: `npm run dev` | `http://localhost:3000` abre |

- [ ] 2.1 a 2.5 no ar.

> Se as APIs já estiverem rodando fora do Eclipse (por exemplo, iniciadas pelo Claude), a porta estará ocupada. Pare o processo da porta (`Get-NetTCPConnection -LocalPort 8081` no PowerShell mostra o PID) antes de subir no Eclipse.
>
> **Depois de qualquer alteração em `vis_business_jobsnow` ou `jb_business_jobsnow`**: `mvn -o install -DskipTests` no módulo e reinicie a API do vis **e** o leitor do bot. O leitor do bot executa código do vis (a aprovação/rejeição roda dentro dele).

---

## 3. Começar do zero (recomendado)

Os roteiros supõem que nenhuma sugestão foi feita ainda. Para isso:

- [ ] 3.1 Rode `executaCcpCreateEntities.bat` na raiz do workspace (ou, no Eclipse, `com.ccp.random.CcpCreateEntities` do projeto `ccp_rest-api-tests_jobsnow`). Sem argumentos, ele recria **jn, vis e jb**, sem pedir nada (desde 2026-10-11 não há mais a janela de escolha). Para recriar só alguns, passe-os como argumentos (`executaCcpCreateEntities.bat vis`); recriar só o jn apaga os modelos de e-mail que o vis semeia nos índices do jn. **Obrigatório na primeira vez depois das mudanças de 2026-10-08**: mudaram a chave da tabela de usuários ignorados (agora só o e-mail), a ordem dos parâmetros do `/fixSkillHierarchy` e os textos do bot — índices antigos fazem o bot responder com os textos e o formato antigos. Desde 2026-10-09 a recriação também cria `jn_support_cancelled_command` (a desistência tira o ticket do `/pendingTickets`) e semeia os nomes "aprovado"/"reprovado" do painel Motivo. **Obrigatório de novo depois das mudanças de 2026-10-11**: a recriação cria `vis_skill_synonym` (sinônimos das sugestões), semeia os e-mails de aprovação/rejeição com "Justificativa do suporte:" e os textos do comando `/listarUsuariosIgnorados`. **Obrigatório de novo depois das mudanças de 2026-10-15**: a recriação cria `vis_resume_linkedin` (dono de cada endereço do LinkedIn, com o aviso ao suporte quando outro e-mail usa o mesmo endereço), `vis_skill_suggestion_daily_limit` e `vis_skill_fix_hierarchy_daily_limit` (uma sugestão de cada tipo por dia).
- [ ] 3.2 Confira que `C:\logs\jn\mappingJnEntitiesErrors.json`, `C:\logs\vis\mappingJnEntitiesErrors.json` e `C:\logs\jb\mappingJnEntitiesErrors.json` estão **vazios**.
- [ ] 3.3 Reinicie a API do vis e o leitor do bot (eles guardam cache em memória).

---

## 4. Fazer login depois de recriar os índices

Recriar o jn apaga o seu login, mas o navegador ainda se lembra dele e entra num laço ("O seu login não foi encontrado"). Resolva assim:

- [ ] 4.1 Abra `http://localhost:3000`, aperte **F12 → Console** e execute: `localStorage.removeItem('logins'); sessionStorage.removeItem('login')` (a sessão da aba fica no `sessionStorage`. Sem apagá-la, a tela continua usando o login antigo, inclusive ao trocar de conta no S8 do roteiro 01)
- [ ] 4.2 O login será pedido quando você **enviar** a primeira sugestão (abrir os modais não exige login). Quando ele aparecer:
  1. Informe `onias85@gmail.com` → **Avançar**.
  2. "Por favor, confirme o e-mail": digite o e-mail de novo → **Confirmar**.
  3. "Informe suas preferências e objetivos": deixe como está → **Enviar**.
  4. "Criando uma nova senha": senha e confirmação (8+ caracteres, maiúscula, número e caractere especial) e o **token**.
  5. O token está no arquivo `C:\logs\email\com.jn.business.messages.JnMessages$JnNotifyUserAboutLoginToken.html` (abra no navegador e procure "esse token é ...").
  6. **Salvar senha** → aparece "Sucesso!!! O usuário 'onias85@gmail.com' foi autenticado com sucesso!".
- [ ] 4.3 Depois do login, a ação que pediu o login (o envio da sugestão) é **refeita sozinha** — não clique em Enviar de novo.

---

## 5. Preparar a tela (usada pelos dois roteiros)

- [ ] 5.1 Abra `http://localhost:3000/portuguese-version/como-estou-indo/ver-meu-curriculo`
- [ ] 5.2 "Função / papel / emprego / ocupação que estou buscando:" → `Programador Beta`
- [ ] 5.3 "Endereço (URL) para encontrar o meu linkedin:" → `https://www.linkedin.com/in/onias85/`
- [ ] 5.4 "Todo o texto que copiei do meu currículo" → todo o conteúdo de `C:\eclipse-workspaces\ccp\cv.txt`
- [ ] 5.5 Clique em **Idiomas** e aguarde.
- [ ] 5.6 Vá para a aba **Habilidades**. Esperado: três colunas — **Conhecimentos implícitos (36)**, "Habilidades pelas quais eu NÃO quero que o meu currículo seja encontrado" (vazia) e "Habilidades pelas quais eu quero que o meu currículo seja ENCONTRADO (105)", com o link **"Deixamos de listar alguma habilidade?"**.

> **LinkedIn:** o endereço precisa terminar em letra, número, `_` ou `%` (pode ter `/` no fim). `https://www.linkedin.com/in/fulano-/` é recusado com 422 desde 2026-10-14.
>
> **Cache da leitura do currículo:** a lista de habilidades fica guardada por 1 hora para o mesmo texto. Quando um roteiro pedir para **"reprocessar o currículo"**, acrescente um espaço no fim do texto do currículo e clique em **Idiomas** de novo — assim a leitura é refeita.

---

## 5A. Uma sugestão de cada tipo por dia (desde 2026-10-15)

Cada sugestão manda um e-mail ao candidato e abre um ticket ao operador. Por isso o candidato pode enviar **uma sugestão de habilidade e um pedido de ajuste de hierarquia a cada 24 horas**. Os dois modais avisam do limite antes do envio ("Atenção: você pode enviar apenas uma sugestão de ... a cada 24 horas"). A partir da segunda sugestão do mesmo tipo nas 24 horas seguintes à primeira, o vis responde **429** e a tela mostra **"Limite de 24 horas atingido"**. O limite não vira à meia-noite: dura 24 horas a partir do envio.

As recusas que não mandam nada vêm antes do limite e **não gastam** a sugestão do dia: habilidade já conhecida (412), já pendente (409), já sugerida por sinônimo (409), já rejeitada ou já avaliada (410), usuário ignorado (403).

Os roteiros 01 e 02 enviam várias sugestões com o mesmo candidato. **Antes de cada cenário que envia uma sugestão**, libere o dia do candidato (o registro não tem cache, então apagá-lo no Elasticsearch basta):

```powershell
# libera a sugestão de habilidade do dia (todos os candidatos; ambiente local)
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/jn_disposable_record/_delete_by_query?refresh=true' -Body '{"query":{"term":{"entity":"vis_skill_suggestion_daily_limit"}}}'
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/vis_skill_suggestion_daily_limit/_delete_by_query?refresh=true' -Body '{"query":{"match_all":{}}}'
# libera o pedido de ajuste de hierarquia do dia
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/jn_disposable_record/_delete_by_query?refresh=true' -Body '{"query":{"term":{"entity":"vis_skill_fix_hierarchy_daily_limit"}}}'
Invoke-RestMethod -Method Post -ContentType 'application/json' -Uri 'http://localhost:9200/vis_skill_fix_hierarchy_daily_limit/_delete_by_query?refresh=true' -Body '{"query":{"match_all":{}}}'
```

---

## 6. Onde conferir os resultados

### 6.1 E-mails (gravados em arquivo, não são enviados de verdade)

Pasta `C:\logs\email\`. Cada modelo tem **um arquivo, sobrescrito a cada envio** — confira a data/hora de modificação.

| Arquivo | Quando é gerado |
|---|---|
| `com.vis.messages.VisMessages$VisNotifySupportAndUserAboutPendingSkillRequest.html` | sugestão de habilidade recebida |
| `com.vis.messages.VisMessages$VisNotifyUserAboutAprovedSkill.html` | habilidade aprovada |
| `com.vis.messages.VisMessages$VisNotifyUserAboutRejectedSkill.html` | habilidade rejeitada |
| `com.vis.messages.VisMessages$VisNotifySupportAndUserAboutPendingSkillHierarchyRequest.html` | ajuste de hierarquia recebido |
| `com.vis.messages.VisMessages$VisNotifyUserAboutFulfiledSkillHierarchy.html` | ajuste de hierarquia avaliado |
| `com.vis.messages.VisMessages$VisNotifyUserAboutAlreadyReviewedSkillHierarchy.html` | ajuste recusado por já ter sido atendido |

### 6.2 Telegram

O aviso ao operador chega **de verdade** no seu Telegram, no chat do bot de suporte, enviado pela API do vis. As respostas do bot também.

### 6.3 Elasticsearch (abra as URLs no navegador)

O e-mail é gravado como **hash** — por isso as consultas filtram pela habilidade ou pelo termo, nunca pelo e-mail.

| O que | URL |
|---|---|
| Sugestões de habilidade pendentes | `http://localhost:9200/vis_skill_pending/_search?pretty` |
| … aprovadas | `http://localhost:9200/vis_skill_approved/_search?pretty` |
| … rejeitadas | `http://localhost:9200/vis_skill_rejected/_search?pretty` |
| Uma habilidade do sistema | `http://localhost:9200/vis_skill/_search?pretty&q=skill:%22PICK%20BY%20LIGHT%22` |
| Pedidos de ajuste pendentes | `http://localhost:9200/vis_skill_fix_hierarchy_pending/_search?pretty` |
| … avaliados | `http://localhost:9200/vis_skill_fix_hierarchy_fulfiled/_search?pretty` |
| Itens de ajuste pendentes / aprovados / rejeitados | `.../vis_skill_fix_hierarchy_item_pending/_search?pretty`, `.../vis_skill_fix_hierarchy_item_approved/...`, `.../vis_skill_fix_hierarchy_item_rejected/...` |
| Sinônimos das sugestões, cada um apontando para a habilidade sugerida | `http://localhost:9200/vis_skill_synonym/_search?pretty` |
| Sugestões do dia (uma por candidato; bloqueiam a segunda com 429) | `http://localhost:9200/jn_disposable_record/_search?pretty&q=entity:vis_skill_suggestion_daily_limit` e `...&q=entity:vis_skill_fix_hierarchy_daily_limit` |
| Dono de cada endereço do LinkedIn (o e-mail é hash) | `http://localhost:9200/vis_resume_linkedin/_search?pretty` |
| Usuários ignorados pelo suporte (o e-mail legível fica dentro de `description`) | `http://localhost:9200/vis_command_not_allowed_to_user/_search?pretty` |
| … que voltaram a ser atendidos | `http://localhost:9200/vis_command_reallowed_to_user/_search?pretty` |
| Caixa de tickets do operador | `http://localhost:9200/jn_support_pending_command/_search?pretty` e `http://localhost:9200/jb_pending_tickets/_search?pretty` |
| Histórico de versões | `http://localhost:9200/jn_versionable/_search?pretty&q=entity:vis_skill_pending` |

### 6.4 Rede do navegador

F12 → **Network**, filtro `8081`: mostra cada chamada da tela e o código HTTP de resposta (200, 400, 403, 404, 409, 410, 412, 422, 429).

---

## 7. Comandos do operador que valem para os dois roteiros

| Comando | Para quê |
|---|---|
| `/pendingTickets` | ver os comandos que o bot mandou e você ainda não executou; responda `1` para resolver o ticket mostrado, `2` para ir ao próximo |
| `/allowCommandToUser <email>` | voltar a atender um usuário ignorado. O "ignorar" vale para todos os comandos, então desfazê-lo também. |
| `/listarUsuariosIgnorados` (ou `/ignoredUsers`) | ver os usuários que o suporte está ignorando, um por vez, como no `/pendingTickets`: responda `1` para voltar a atender o usuário mostrado (roda o `/allowCommandToUser` dele e mostra a lista de novo) ou `2` para ir ao próximo |
| `/reviewSkillSuggestion <email> <habilidade>` | revisar uma sugestão de habilidade (roteiro 01); chega pronto no Telegram, basta reenviar |
| `/fixSkillHierarchy add <email> <termo>` ou `/fixSkillHierarchy remove <email> <termo>` | revisar um pedido de ajuste de hierarquia (roteiro 02); chega pronto no Telegram, basta reenviar |
| qualquer comando | abandonar a conversa em andamento com o bot (útil se você se perder no meio de um comando): digitar um comando, inclusive o mesmo, descarta a conversa e recomeça. **Não existe `/removeSession`**: digitado no meio de uma revisão, ele é lido como resposta. |
| `/showAllCommands` | listar os comandos do bot |
