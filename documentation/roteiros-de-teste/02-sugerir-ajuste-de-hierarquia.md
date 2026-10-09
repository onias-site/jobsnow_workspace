# Roteiro 02 — Sugerir ajuste na hierarquia de conhecimentos (⊕ e 🗑 dos conhecimentos implícitos)

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) feito até o item 5 (tela na aba Habilidades).

> **Executado de verdade em 2026-10-08**, no navegador (conta `roteiro.login2@teste.com`) e com o bot de suporte, de H1 a H11, menos o H9 (precisa de um segundo login) e o 8.7. Os termos e as habilidades abaixo são os que a tela mostrou nesse dia. O que a execução revelou está nas notas **"Visto na execução"** e na seção [Observações da execução](#observações-da-execução-2026-10-08) no fim.

## Como a funcionalidade funciona (resumo)

1. Na coluna **Conhecimentos implícitos**, cada título (ex.: `ORMJAVA (2)`) é um conhecimento que o sistema deduziu do currículo, com as habilidades que dependem dele.
2. **⊕ (associar):** o candidato escolhe habilidades do **seu currículo** que, para ele, também dependem daquele conhecimento. **🗑 (desassociar):** escolhe, entre as habilidades listadas no conhecimento, as que **não** dependem dele. Nos dois casos ele justifica (10 a 500 caracteres).
3. O pedido fica **pendente** (`vis_skill_fix_hierarchy_pending`, chave e-mail + termo + tipo) e é quebrado em **itens**, um por habilidade (`vis_skill_fix_hierarchy_item_pending`, chave termo + tipo + habilidade — **sem e-mail**: o item é compartilhado entre candidatos que pedem a mesma coisa).
4. Enquanto pendente, o modal é **só leitura**. Para alterar o pedido, o candidato desiste dele e envia de novo.
5. O candidato recebe um e-mail; o operador recebe `/fixSkillHierarchy <add|remove> <email> <termo>`. O termo vai por último, então pode ter espaços (`JAVA SERVER`).
6. O operador aprova tudo, rejeita tudo ou decide **item a item** (sempre com justificativa), ou ignora o candidato — e o "ignorar" vale para **todos os comandos** do suporte. Itens decididos em revisões anteriores (aprovados **ou** reprovados) não são perguntados de novo.
7. O pedido vai sempre para **avaliado** (`vis_skill_fix_hierarchy_fulfiled`); cada item vai para **aprovado** ou **rejeitado**. Um item aprovado altera os "pais" da habilidade em `vis_skill` **e** na tabela que a leitura do currículo usa, então o conhecimento implícito da tela muda. O candidato recebe um e-mail com os itens aprovados e rejeitados e as justificativas.
8. Um pedido cujas habilidades **todas** já foram decididas antes (mesmo termo e tipo) não é gravado: o candidato recebe o e-mail "já foram atendidos".

> **Cache:** a tabela que a leitura do currículo usa fica 1 hora em memória na API do vis, e a aprovação roda no leitor do bot, outro processo. Para ver na tela o efeito de uma aprovação (1.19, 4.7), **reinicie a API do vis** e reprocesse o currículo.

## Dados usados neste roteiro (do `cv.txt`, conferidos na tela em 2026-10-08)

| Conhecimento implícito | Habilidades listadas nele | Uso |
|---|---|---|
| `ORMJAVA (2)` | HIBERNATE, JPA | H1, H2, H3, H6 (⊕) |
| `SQLDATABASE (11)` | BIGQUERY, DB2, HIBERNATE, JDBC, JPA, LINQ, MYSQL, ORACLE, ORM, PL/SQL, SQL SERVER | H4, H5 (🗑), H7 (⊕) |
| `NOSQLDATABASE (2)` | DATASTORE, ELASTICSEARCH | H8 |
| `JAVA SERVER (13)` | EJB, JBOSS, JSF, JSP, PRIMEFACES, SERVLETS, SPRINGBOOT, STRUTS, TOMCAT, VELOCITY, VRAPTOR, WEBLOGIC, WEBSPHERE | H11 (termo com espaço) |

> A taxonomia muda quando alguém aprova ajustes. Antes de começar, abra os títulos acima e confira as habilidades; se mudaram, escolha outras equivalentes. Os itens não têm e-mail na chave, então um item já decidido por outro candidato (ou por uma execução anterior deste roteiro) não é perguntado de novo. Confira `vis_skill_fix_hierarchy_item_approved` e `..._item_rejected` antes.

---

## H1 — Associar, revisão item a item (aprova um, rejeita outro)

### Candidato

- [ ] 1.1 Na coluna Conhecimentos implícitos, localize **ORMJAVA (2)**. Clique no título: abre a lista "Habilidades associadas a ORMJAVA": 1: HIBERNATE, 2: JPA.
- [ ] 1.2 Clique no **⊕** ao lado de `ORMJAVA (2)`. Esperado: o accordion **não** abre/fecha nem muda a URL; abre o modal "Sugira adicionar (presentes no seu currículo) que você acredita que dependem do conhecimento em ORMJAVA", com uma lista de seleção ("Selecione as habilidades do seu currículo") e um texto ("Explique por que as habilidades selecionadas acima deveriam ser associadas a ORMJAVA"). Nenhum status aparece.
- [ ] 1.3 Abra a lista: ela traz as habilidades do seu currículo **menos** HIBERNATE e JPA (104 de 106). Use o filtro: digite `jdb` → aparece só JDBC.
- [ ] 1.4 Selecione **JDBC** e **SPRING**. Justificativa: `JDBC e Spring são usados junto com ORM em todo projeto Java que fiz.`
- [ ] 1.5 **Enviar**. (Se pedir login, faça o item 4 da preparação; o envio é refeito sozinho.)

Esperado:
- [ ] "Sugestão enviada — Obrigado! Sua sugestão será analisada e você será avisado do resultado." O modal fecha. Network: `POST /resume/<email>/skills/hierarchy` → 200.
- [ ] E-mail `...$VisNotifySupportAndUserAboutPendingSkillHierarchyRequest.html`: "Olá, você solicitou associação entre os termos JDBC, SPRING e ORMJAVA. Nosso time está avaliando e te responderá o quanto antes."
- [ ] Telegram: `/fixSkillHierarchy add <email> ORMJAVA`
- [ ] `vis_skill_fix_hierarchy_pending`: o pedido (`parent: ORMJAVA`, `type: add`, `skill: [JDBC, SPRING]`, `description`).
- [ ] `vis_skill_fix_hierarchy_item_pending`: **dois** itens (`ORMJAVA/add/JDBC` e `ORMJAVA/add/SPRING`).

### Candidato reabre o modal (pendente = só leitura)

- [ ] 1.6 Clique no ⊕ de ORMJAVA de novo. Esperado:
  - o botão principal mostra o carregamento;
  - JDBC e SPRING vêm selecionados e a justificativa preenchida, **ambos desabilitados**;
  - aparecem **"status: Pendente"** e o aviso "Esta sugestão está em análise. Para alterá-la, desista dela e envie uma nova.";
  - os botões são **"Desistir da sugestão"** e **"Fechar"** (não há "Enviar").
- [ ] 1.7 Clique em **Fechar**: o modal fecha sem enviar nada.

### Operador

- [ ] 1.8 Envie ao bot `/fixSkillHierarchy add <email> ORMJAVA`. Esperado:

```
Solicitação de associação de <email> para o termo ORMJAVA

[associação]
Justificativa do usuário: JDBC e Spring são usados junto com ORM em todo projeto Java que fiz.
Itens pendentes: JDBC, SPRING

Responda com uma das opções:
• aprovar <justificativa> — aprova todos os itens pendentes
• rejeitar <justificativa> — rejeita todos os itens pendentes
• um a um — decide item por item
• ignorar — descarta a solicitação e ignora as próximas deste usuário em todos os comandos
```

- [ ] 1.9 Responda `aprovar` (sem justificativa). Esperado: "Não entendi a resposta. Toda decisão precisa vir acompanhada de uma justificativa." + as opções.
- [ ] 1.10 Responda `um a um`. Esperado: "Item 1 de 2: JDBC (associação com o termo ORMJAVA) — Responda: aprovar <justificativa> ou rejeitar <justificativa>".
- [ ] 1.11 Responda `aprovar JDBC é a base sobre a qual os ORMs Java funcionam`. Esperado: "Item 2 de 2: SPRING ...".
- [ ] 1.12 Responda `rejeitar Spring é um framework de aplicação, não depende de ORM`. Esperado:

```
Revisão concluída para <email> / ORMJAVA.
Aprovados: JDBC
Reprovados: SPRING
O usuário será avisado por e-mail.
```

### Conferir

- [ ] 1.13 `vis_skill_fix_hierarchy_pending`: sem o pedido. `vis_skill_fix_hierarchy_fulfiled`: o pedido, com `explanation` contendo uma linha por item (`JDBC (approved): ...`, `SPRING (rejected): ...`).
- [ ] 1.14 Itens: `ORMJAVA/add/JDBC` em `..._item_approved`; `ORMJAVA/add/SPRING` em `..._item_rejected`; nenhum em `..._item_pending`.
- [ ] 1.15 `vis_skill?q=skill:JDBC`: o campo `parent` agora inclui `ORMJAVA`. `vis_skill?q=skill:SPRING`: **sem** ORMJAVA.
- [ ] 1.16 E-mail `...$VisNotifyUserAboutFulfiledSkillHierarchy.html`: "Olá, a sua solicitação de associação com o termo ORMJAVA foi avaliada pelo nosso time." + "Itens aprovados:" (JDBC e a justificativa) + "Itens reprovados:" (SPRING e a justificativa).
- [ ] 1.17 Ticket `/fixSkillHierarchy add <email> ORMJAVA` saiu de `/pendingTickets`.
- [ ] 1.18 Na tela, clique no ⊕ de ORMJAVA. Esperado: **"status: Avaliado"**, painel **"Motivo"** com as duas linhas (uma embaixo da outra), campos desabilitados, botão **"Nova sugestão"** (sem "Desistir"). JDBC e SPRING aparecem selecionados mesmo que deixem de ser opções.
  > **Visto na execução:** as duas linhas do Motivo apareciam coladas numa linha só. **Corrigido** em 2026-10-08 (`TabSkills.tsx`: o parágrafo do Motivo passou a respeitar a quebra de linha). As linhas trazem `(approved)` / `(rejected)` em inglês, como estão gravadas — ⚠ ver as observações.
- [ ] 1.19 **A aprovação aparece na tela:** feche o modal, **reinicie a API do vis** (cache, ver o resumo), **reprocesse o currículo** (espaço no fim do texto + **Idiomas**) e volte à aba Habilidades. Esperado: **ORMJAVA (3)** lista HIBERNATE, **JDBC**, JPA.
  > **Visto na execução:** confirmado na tela (`ORMJAVA (2)` → `ORMJAVA (3)`).

---

## H2 — Pedido refeito com item já decidido

> Depois do 1.19, JDBC já está em ORMJAVA e **sai das opções do ⊕** — por isso o item já decidido usado aqui é o SPRING (reprovado no H1). Se você pulou o 1.19, pode usar JDBC (já aprovado) e o resumo dirá "Já aprovados anteriormente".

- [ ] 2.1 Ainda no ⊕ de ORMJAVA (status Avaliado), clique em **Nova sugestão**: seleção e justificativa se esvaziam e voltam a ficar habilitadas.
- [ ] 2.2 Selecione **SPRING** (já reprovado em H1) e **MYSQL** (novo). Justificativa: `MySQL também é acessado via ORM nos projetos citados.` → **Enviar** → "Sugestão enviada".
- [ ] 2.3 E-mail de recebimento lista **MYSQL, SPRING**.
- [ ] 2.4 Operador: `/fixSkillHierarchy add <email> ORMJAVA`. Esperado: "Itens pendentes: MYSQL" e "Já reprovados anteriormente (não serão perguntados): SPRING".
- [ ] 2.5 Responde `rejeitar MySQL é banco de dados, não framework de mapeamento`. Esperado: "Aprovados: -" e "Reprovados: SPRING, MYSQL" — o SPRING entra no resumo com a decisão anterior.
- [ ] 2.6 E-mail de avaliação: em "Itens reprovados", SPRING com a justificativa "item já reprovado em revisão anterior" e MYSQL com a sua.

---

## H3 — Pedido recusado por já ter sido atendido

- [ ] 3.1 ⊕ de ORMJAVA → **Nova sugestão** → selecione só **SPRING** (decidido em H1) → justificativa `Reenviando um pedido já atendido antes.` → **Enviar**.
- [ ] 3.2 Esperado: **nada fica pendente** e **nada chega ao Telegram**. Na tela: **"Sugestão enviada"** (Network 200).
- [ ] 3.3 E-mail `...$VisNotifyUserAboutAlreadyReviewedSkillHierarchy.html`: "Olá, você solicitou associação entre os termos SPRING e ORMJAVA, mas todos eles já foram atendidos em solicitações anteriores, por isso esta solicitação não foi registrada."

> **⚠ Visto na execução (para a sua decisão):** a tela diz "Sugestão enviada" para um pedido que **não** foi registrado; só o e-mail avisa o candidato. Ao reabrir o ⊕, a tela mostra o pedido avaliado anterior, não o recusado.

---

## H4 — Desassociar (🗑), aprovar tudo de uma vez

- [ ] 4.1 Clique no **🗑** de `SQLDATABASE`. Esperado: modal "Sugira remover habilidades que você acredita que não dependem do conhecimento em SQLDATABASE"; a lista traz **só** as 11 habilidades listadas em SQLDATABASE.
- [ ] 4.2 Selecione **LINQ**. Justificativa: `LINQ é do mundo .NET e não depende de banco SQL.` → **Enviar**.
- [ ] 4.3 E-mail: "Olá, você solicitou **desassociação** entre os termos LINQ e SQLDATABASE ...". Telegram: `/fixSkillHierarchy remove <email> SQLDATABASE`.
- [ ] 4.4 Operador envia o comando. Esperado: cabeçalho "Solicitação de **desassociação** ..." e só o item LINQ.
- [ ] 4.5 Responde `aprovar LINQ realmente é de outra plataforma`. Esperado: "Aprovados: LINQ", "Reprovados: -".
- [ ] 4.6 `vis_skill?q=skill:LINQ`: `parent` **sem** SQLDATABASE (se a consulta logo depois ainda mostrar, recarregue em 1 s — refresh do Elasticsearch). E-mail de avaliação: "desassociação com o termo SQLDATABASE", só "Itens aprovados" (sem o bloco de reprovados).
- [ ] 4.7 Reinicie a API do vis e reprocesse o currículo. Esperado: **SQLDATABASE (10)**, sem LINQ.
  > **Visto na execução:** confirmado na tela (`SQLDATABASE (11)` → `(10)`).
- [ ] 4.8 Na tela: 🗑 de SQLDATABASE mostra o pedido avaliado (LINQ); ⊕ de SQLDATABASE abre vazio, com **Enviar**. Um não interfere no outro.

---

## H5 — Rejeitar tudo de uma vez

- [ ] 5.1 🗑 de SQLDATABASE → **Nova sugestão** → selecione **JPA** e **HIBERNATE** → `Os dois são frameworks e não dependem de banco SQL.` → Enviar.
- [ ] 5.2 Operador: `/fixSkillHierarchy remove <email> SQLDATABASE` → `rejeitar ambos são implementações que usam banco SQL`.
- [ ] 5.3 Esperado: "Aprovados: -", "Reprovados: JPA, HIBERNATE"; o pedido vai para avaliado; os dois itens para rejeitados; `vis_skill` de JPA e HIBERNATE continuam com SQLDATABASE; e-mail só com "Itens reprovados".

---

## H6 — Validações e desistência

### Validações (nada vai ao servidor)
- [ ] 6.1 ⊕ de ORMJAVA → **Nova sugestão** → **Enviar** sem selecionar nada. Esperado: "Nenhuma habilidade selecionada — Selecione ao menos uma habilidade para associar a ORMJAVA."
- [ ] 6.2 Selecione **ORACLE**, justificativa `curta` → Enviar. Esperado: "Explicação inválida — A explicação deve ter entre 10 e 500 caracteres."
- [ ] 6.3 No 🗑 de ORMJAVA, sem selecionar → "Selecione ao menos uma habilidade para desassociar de ORMJAVA."

### Desistir
- [ ] 6.4 Faça o pedido de associação de **ORACLE** em ORMJAVA com uma justificativa válida (`Oracle é acessado por ORM nos projetos.`).
- [ ] 6.5 Reabra o ⊕ → "status: Pendente", campos desabilitados → **Desistir da sugestão** → **Sim, desistir**. Esperado: "Sugestão retirada — Sua sugestão não será mais analisada."; o pedido some de `..._pending`; o item `ORMJAVA/add/ORACLE` some de `..._item_pending` (nenhum outro pedido o usa).
- [ ] 6.6 Reabra o ⊕. Esperado: o **último pedido avaliado** desse termo e tipo (o do H2, "status: Avaliado", com **Nova sugestão**); clicando em Nova sugestão, dá para mandar o pedido corrigido. Sem histórico anterior, os campos viriam vazios, com **Enviar**.
- [ ] 6.7 Operador envia o comando que tinha chegado. Esperado: "Não há itens pendentes de ajuste (add) na hierarquia de conhecimentos para o e-mail '<email>' e o termo 'ORMJAVA'".

> **409 (opcional, só por fora da tela):** a tela não deixa reenviar um pedido pendente. Se ele chegar ao servidor por outra aba ou pelo Postman, a resposta é **409** e o aviso é "Sugestão já pendente — Você já tem uma sugestão pendente para ORMJAVA. Para alterá-la, desista dela e envie uma nova." (**Visto na execução:** 409 confirmado com o ORACLE pendente.)

---

## H7 — Operador ignora o candidato (vale para todos os comandos)

> Bloqueia o seu e-mail **em todos os comandos** do suporte. O passo 7.7 desfaz.

- [ ] 7.1 ⊕ de **SQLDATABASE** → selecione **ELASTICSEARCH** → `Elasticsearch tem linguagem de consulta própria derivada de SQL.` → Enviar.
- [ ] 7.2 Operador: `/fixSkillHierarchy add <email> SQLDATABASE` → `ignorar`. Esperado: "Confirma que o usuário <email> será ignorado pelo suporte, em todos os comandos? ... Responda: sim ou não".
- [ ] 7.3 `não` → "O usuário não será ignorado." + opções. `ignorar` → `sim` → "O usuário <email> foi ignorado pelo suporte, em todos os comandos. A solicitação para o termo SQLDATABASE foi descartada."
- [ ] 7.4 Conferir: pedido e item pendentes descartados, **sem** e-mail ao candidato; `vis_command_not_allowed_to_user` com **um** registro do e-mail, `commandName: fixSkillHierarchy` e o pedido descartado na `description`.
- [ ] 7.5 Candidato repete o pedido. Esperado: aviso vermelho "Falha ao enviar sugestão" (Network **403**); nada pendente; nada no Telegram.
- [ ] 7.6 **Ignorar é global:** o candidato tenta sugerir uma habilidade **desconhecida** ("Deixamos de listar alguma habilidade?", ex.: `GEORREFERENCIAMENTO`). Esperado: também **403** / "Falha ao enviar sugestão". (Com uma habilidade já conhecida, o 412 vem antes do 403.) Se o operador rodar qualquer um dos dois comandos para esse e-mail, o bot responde: "O usuário <email> está sendo ignorado pelo suporte e as solicitações dele não são atendidas em nenhum comando. Para voltar a atendê-lo, use /allowCommandToUser <email>"
- [ ] 7.7 Operador: `/allowCommandToUser <email>`. Esperado: "O usuário <email> não é mais ignorado pelo suporte: as próximas solicitações dele, em todos os comandos, voltarão a chegar ao suporte."
- [ ] 7.8 Candidato repete 7.5. Esperado: agora "Sugestão enviada" e o comando chega ao Telegram. (Ele é resolvido no H10.3.)

---

## H8 — Pelo `/pendingTickets`

- [ ] 8.1 Crie dois pedidos: ⊕ de **NOSQLDATABASE** com **MEMCACHE** e 🗑 de **NOSQLDATABASE** com **DATASTORE** (justificativas válidas).
- [ ] 8.2 Operador: `/pendingTickets`. Esperado: "Você tem N tickets para resolver" e "Ticket 1 de N => ..." com "Digite "1" para resolver ou "2" para ir ao próximo". Os novos estão no fim (ordem do mais antigo para o mais novo).
- [ ] 8.3 `2` → mostra o próximo. `3` → "Não entendi a resposta." e o mesmo ticket.
- [ ] 8.4 Ao chegar no `/fixSkillHierarchy add <email> NOSQLDATABASE`, responda `1`. Esperado: "Resolvendo o ticket ..." e o pedido de NOSQLDATABASE (associação) com as opções.
- [ ] 8.5 Decida (`aprovar ...`). Esperado: o resumo da revisão e, em seguida, a lista de tickets reaberta sem esse.
- [ ] 8.6 Resolva o `/fixSkillHierarchy remove <email> NOSQLDATABASE` digitando o comando à mão (fora da lista). Depois, `/pendingTickets` não o mostra mais (digitar avulso também dá baixa).
- [ ] 8.7 Quando não houver mais nenhum: "Você não tem tickets para resolver." (Não executado em 2026-10-08: a base local tem 20 tickets de testes automáticos.)

---

## H9 — Dois candidatos pedindo a mesma coisa (opcional; precisa de um segundo login)

O item não tem e-mail na chave. Para ver isso:
- [ ] 9.1 Com outro e-mail (outra janela anônima, com o login da preparação para esse e-mail), peça ⊕ de **ORMJAVA** com **ORACLE**. Com o seu, peça o mesmo.
- [ ] 9.2 Existe **um** item `ORMJAVA/add/ORACLE` pendente e **dois** pedidos.
- [ ] 9.3 Um dos candidatos desiste: o item **continua** pendente (o outro pedido ainda o usa). O outro desiste: o item some.
- [ ] 9.4 Variante: em vez de desistir, o operador aprova o pedido do primeiro. Ao revisar o do segundo, ORACLE aparece como "Já aprovados anteriormente" e a revisão termina sozinha (nada a perguntar).

---

## H10 — Comandos malformados do operador

- [ ] 10.1 `/fixSkillHierarchy xyz <email> ORMJAVA` → "Não há itens pendentes de ajuste (xyz) na hierarquia de conhecimentos para o e-mail '<email>' e o termo 'ORMJAVA'".
- [ ] 10.2 `/fixSkillHierarchy add <email> TERMOINEXISTENTE` → mesma mensagem, com o termo.
- [ ] 10.3 Abandonar uma revisão no meio: com o pedido do 7.8 pendente, envie `/fixSkillHierarchy add <email> SQLDATABASE` e, em vez de responder, **digite o comando de novo** (ou qualquer outro comando). Esperado: a revisão recomeça do início; o pedido continua pendente. Termine com `rejeitar Elasticsearch não é banco SQL`.
  > **Visto na execução:** **não existe** comando `/removeSession` (não aparece no `/showAllCommands`). Digitado no meio de uma revisão, ele é lido como resposta e o bot diz "Não entendi a resposta". Para abandonar uma conversa, digite qualquer comando.

---

## H11 — Termo com espaço

- [ ] 11.1 ⊕ de **JAVA SERVER** → selecione **JERSEY** → `Jersey roda dentro de um servidor Java como Tomcat ou JBoss.` → Enviar.
- [ ] 11.2 O Telegram recebe `/fixSkillHierarchy add <email> JAVA SERVER`. Envie ao bot.
- [ ] 11.3 Esperado: "Solicitação de associação de <email> para o termo JAVA SERVER" com o item. Decida e confira que o resumo cita "JAVA SERVER" inteiro e o pedido vai para avaliado com `parent: JAVA SERVER`.

---

## Resumo do que este roteiro cobre

| Regra | Cenário |
|---|---|
| Opções do ⊕ (currículo menos os já associados) e do 🗑 (só os associados) | H1, H4 |
| Consulta ao abrir o modal: Pendente (só leitura, "Fechar") / Avaliado + Motivo ("Nova sugestão"); Desistir | H1, H2, H6 |
| Item a item, aprovar tudo, rejeitar tudo; justificativa obrigatória | H1, H4, H5 |
| Itens decididos antes não são perguntados e entram no resumo e no e-mail | H2, H9 |
| Pedido só com itens já decididos é recusado e avisado por e-mail | H3 |
| Item compartilhado entre candidatos; desistência só apaga item órfão | H6, H9 |
| Aprovação altera `vis_skill.parent` e o conhecimento implícito da tela | H1, H4 |
| Ignorar com confirmação, global (403 nos dois modais); `/allowCommandToUser <email>` | H7 |
| `/pendingTickets`: entra, "1", "2", baixa avulsa | H8 |
| Comando malformado; abandonar revisão; termo com espaço | H10, H11 |

## Observações da execução (2026-10-08)

| # | O que se viu | Situação |
|---|---|---|
| 1 | Motivo com as linhas de cada item coladas numa só (1.18). | **corrigido** (`TabSkills.tsx`) |
| 2 | Pedido recusado por já atendido: a tela diz "Sugestão enviada" (H3). | ⚠ para a sua decisão |
| 3 | O Motivo mostra `(approved)` / `(rejected)` em inglês para o candidato. É o texto gravado em `explanation`. | ⚠ para a sua decisão |
| 4 | `/removeSession`, citado neste roteiro e na preparação, não existe (10.3). | documentação corrigida |
| 5 | `/showAllCommands` lista `/solucionarTicketsDeTokenDeLogin`, mas os tickets de login usam `/solveLoginTokenTicket`. | ⚠ para a sua avaliação |
| 6 | Aprovação só aparece na tela depois de 1 hora ou de reiniciar a API do vis. | ambiente / cache |
| 7 | `vis_command_not_allowed_to_user` tem registros duplicados de um e-mail antigo (chaves de antes da mudança para "só e-mail"). Recriar o índice (item 3.1 da preparação) limpa. | ambiente |
