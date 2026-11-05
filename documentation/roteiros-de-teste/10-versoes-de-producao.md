# Roteiro 10 — Versões de produção dos roteiros 01 a 09

**Pré-requisito:** deploy em dia (`/ccp-deploy` e `07-publicar-na-vm.ps1`), `scripts/checar-producao.py` limpo e o túnel do ES de produção aberto só para conferir e apagar (`gcloud compute ssh ... --tunnel-through-iap -- -L 9210:localhost:9200 -N`), e os subdomínios de teste da seção S entregando no Gmail.

> **Criado em 2026-11-03.** Reescrito em 2026-11-04 com os subdomínios de teste (seção S): os recrutadores profissionais deixam de depender do local. Ainda não executado por inteiro (a parte sem login da seção F rodou em 2026-11-04).

## Regras invioláveis

1. **Nunca** resetar a base de produção, nem rodar `CcpCreateEntities` contra ela.
2. Toda conta, currículo, ticket e recrutador criado pelo teste vai para a **planilha de limpeza** (seção L). No fim, apaga-se só o que está nela.
3. Os candidatos fictícios usam só skills, cargos, pretensões e DDD que existem em currículos reais. Nada de identificador real: e-mail, LinkedIn e nome são inventados.
4. Simulação de carga e estresse **só no local**.
5. O convite aos candidatos legados (`executaConviteDeCurriculos.bat`) **não** é testado em produção.
6. Nenhum segredo de `C:\segredos\producao.json` ou de `application_properties` aparece em saída, arquivo ou chat.
7. Defeito achado: corrigir o código, fazer o deploy, passar os dados com um script numerado em `documentation/deploy` (idempotente, pelo túnel) e **testar de novo o mesmo ponto** antes de seguir.
8. O MX de `onias.site` **não** muda: os subdomínios de teste têm MX próprio, e `curriculos@onias.site` e `privacidade@onias.site` seguem como estão.

## O que muda em relação ao local

| Item | Local | Produção |
|---|---|---|
| Front | `http://localhost:3000` | `https://onias.site` |
| API vis / js | `localhost:8081` / `localhost:8082` | `https://api.onias.site` / `https://login.onias.site` |
| E-mail | mock em `C:\logs\email` | SendGrid real, remetente `curriculos@onias.site`; tudo chega a `onias85@gmail.com` (aliases `+` e pega-tudo dos subdomínios), lido pelo MCP do Gmail ou no Chrome, **inclusive o Spam** |
| Recrutadores de domínio | `@empresa09.com.br`, `@consultoria09.com.br` (fictícios, sem caixa) | `@alfatech.onias.site`, `@betaconsult.onias.site` (subdomínios com pega-tudo) |
| Operador do suporte | `automacao/SupportBotCommand.java` | Telegram real, chat privado com `@onias_site_support_prd_bot`, comandos em português (`/ticketsPendentes`, `/responderFaleConosco`...) |
| Cota diária | `automacao/libera-cota.ps1` | **não liberar**: cada cenário com cota usa uma conta nova |
| Sessão | aberta pela API em `localhost` | aberta pelo próprio modal, no Chrome, pelo usuário (o assistente não digita token nem senha em produção) |
| Mês | — | o Mês/ano das telas abre no mês anterior; escolha o corrente |

## S — Subdomínios de teste (feito uma vez, pelo usuário)

| Subdomínio | Papel | Por quê |
|---|---|---|
| `alfatech.onias.site` | empresa com 2 recrutadores | caso "mesmo domínio" |
| `betaconsult.onias.site` | consultoria com 1 recrutador | caso "outro domínio" |

- [ ] S.1 No provedor de redirecionamento (KingHost, se o plano tiver pega-tudo; ou outro serviço só de redirecionamento), crie um **pega-tudo** para cada subdomínio, com destino `onias85@gmail.com`.
- [ ] S.2 No DNS do KingHost, os registros MX (e o TXT de verificação, se o serviço pedir) **só dos subdomínios**. Nada muda no `onias.site` raiz.
- [ ] S.3 Teste de entrega: do Gmail, mande uma mensagem para `teste-<d>@alfatech.onias.site` e outra para `teste-<d>@betaconsult.onias.site`. As duas chegam (às vezes no Spam, porque o redirecionamento quebra o SPF/DMARC; não atrapalha o teste).
- [ ] S.4 Os nomes não podem coincidir com empresas reais nem com a lista de domínios não profissionais (`NON_PROFESSIONAL_DOMAINS` em `jn_system_message`): os dois contam como recrutador **profissional**.

## Contas

`<d>` = data do teste (ex.: `20261104`).

| Papel | E-mail | Domínio no Quem me viu |
|---|---|---|
| Candidato TI | `onias85+cand-ti-<d>@gmail.com` | — |
| Candidato operacional | `onias85+cand-op-<d>@gmail.com` | — |
| Candidato com LinkedIn emprestado | `onias85+cand-lk-<d>@gmail.com` | — |
| Recrutador 1 do mesmo domínio | `rec1-<d>@alfatech.onias.site` | `alfatech.onias.site` |
| Recrutador 2 do mesmo domínio | `rec2-<d>@alfatech.onias.site` | `alfatech.onias.site` |
| Recrutador de outro domínio | `rec-<d>@betaconsult.onias.site` | `betaconsult.onias.site` |
| Recrutadores freelancers | `onias85+rec-free1-<d>@gmail.com`, `onias85+rec-free2-<d>@gmail.com` | `freelancer` |

Os candidatos ficam nos aliases do Gmail: domínio não importa para eles. `curriculos@onias.site` (recrutador real, caixa do usuário) só entra na seção E.

## Roteiro a roteiro

| Roteiro | Em produção | Ajustes |
|---|---|---|
| 01 Sugerir habilidade | sim | o operador **rejeita** tudo (ou desiste) para não criar habilidades reais; S8 (decisão vale para todos) só com rejeição; uma conta nova por envio, por causa da cota |
| 02 Ajuste de hierarquia | sim | o operador **rejeita tudo**: uma aprovação muda a taxonomia real |
| 03 Login | sim, pela tela | sem `03-modal-de-login.mjs` (ele fala com localhost); bloqueio e desbloqueio com o operador real; tokens no Gmail |
| 04 e 05 Tela do currículo | sim | currículos montados com dados reais anonimizados; C6 avisa o operador real |
| 06 Fale conosco | sim | ver seção F |
| 07 Acessos | sim | — |
| 08 E-mail aos recrutadores | sim, com cuidado | o processo agendado **não** está instalado; o envio é o `SendResumesToRecruiters.java` apontado para produção **só com os recrutadores de teste** nos argumentos (ele grava e envia só para eles); os links levam a `https://onias.site` |
| 09 Dinâmica candidato/recrutador | sim | ver seção D (os 5 recrutadores da tabela de contas) |
| 09 D4 Empresa indesejada | sim | ver seção E |

## D — Dinâmica candidato/recrutador em produção

- [ ] D.1 Os candidatos cand-ti, cand-op e cand-lk criam conta e currículo pela tela (o usuário entra nas contas).
- [ ] D.2 Rode `SendResumesToRecruiters.java` em produção com os 5 recrutadores de teste nos argumentos. Esperado: `emailsSent: 5`, e cada e-mail chega ao Gmail (os 3 de subdomínio pelo pega-tudo) com os 3 candidatos de teste entre os currículos da semana.
- [ ] D.3 Cada recrutador abre candidatos pelo link do e-mail, conforme a matriz abaixo. Anote cada visualização na planilha.

| Candidato | rec1 alfatech | rec2 alfatech | rec betaconsult | free1 | free2 | Quem me viu esperado |
|---|---|---|---|---|---|---|
| cand-ti | ✔ | ✔ | ✔ | ✔ | — | alfatech.onias.site 2, betaconsult.onias.site 1, freelancer 1 (total 4) |
| cand-op | ✔ | — | — | ✔ | ✔ | alfatech.onias.site 1, freelancer 2 (total 3) |
| cand-lk | — | — | ✔ | — | — | betaconsult.onias.site 1 (total 1) |
| **Total por recrutador** | 2 | 1 | 2 | 2 | 1 | **8** |

- [ ] D.4 O mesmo recrutador abre de novo um candidato que já viu: o Quem me viu **não** muda (a 2ª visualização não conta).
- [ ] D.5 **Meu recrutamento › Currículos visualizados** de cada recrutador (o usuário entra na conta): mostra exatamente as visualizações da coluna dele.
- [ ] D.6 **Meus dados › Quem me viu** de cada candidato, no mês corrente: o total e a grade por domínio da última coluna.
- [ ] D.7 cand-lk usa o LinkedIn de outro candidato de teste: a visualização conta para todo e-mail do mesmo LinkedIn, e o suporte recebe o aviso do dono do LinkedIn.
- [ ] D.8 Descadastre `rec-free2` pelo link do e-mail (R5 do roteiro 08). No envio seguinte (outro dia), ele não recebe.

## E — Empresa indesejada em produção

A regra só barra recrutador **profissional**. O nome da empresa, sem acento, espaço e símbolo, barra o recrutador quando é uma das partes do domínio (separadas por ponto e hífen), ou quando tem 4 letras ou mais e aparece dentro do domínio escrito sem pontos e hífens. Freelancer nunca é barrado.

| Empresa indesejada do cand-ti | rec1/rec2 alfatech | rec betaconsult | `curriculos@onias.site` | freelancers |
|---|---|---|---|---|
| `Alfatech` | barrado | recebe | recebe | recebe |
| `Alfa Tech` | barrado | recebe | recebe | recebe |
| `Beta Consult` | recebe | barrado | recebe | recebe |
| `Onias` | barrado | barrado | barrado | recebe |
| (nenhuma) | recebe | recebe | recebe | recebe |

- [ ] E.1 O cand-ti preenche em **Meu currículo** a empresa indesejada `Alfatech` e salva.
- [ ] E.2 Rode `SendResumesToRecruiters.java` com rec1, rec2, rec betaconsult e rec-free1. Esperado: os e-mails de rec1 e rec2 **não** trazem o cand-ti; os de betaconsult e free1 trazem. **Currículos da semana** de cada um mostra o mesmo.
- [ ] E.3 Repita com `Alfa Tech` (normalização) e com `Beta Consult` (só a betaconsult fica sem o candidato).
- [ ] E.4 Repita com `Onias`, incluindo `curriculos@onias.site` nos argumentos: os 3 recrutadores dos subdomínios e `curriculos@onias.site` ficam sem o candidato, porque `onias` é uma parte de todos esses domínios. É o comportamento da regra, não um defeito.
- [ ] E.5 Tire a empresa indesejada e rode o envio de novo: todos recebem o cand-ti.
- [ ] E.6 Planilha de limpeza: a lista da semana de `curriculos@onias.site` em `vis_recruiter_resumes` foi regravada pelo teste. Ela **não** é apagada (o recrutador é real); o próximo envio do processo diário a sobrescreve.

## F — Dinâmica do fale conosco em produção

Vários usuários abrem chamados de tipos diferentes; o operador real atende pelo `@onias_site_support_prd_bot`; cada usuário recebe, pelo SendGrid, só a resposta do seu chamado. Todo título começa com `[TESTE <d>]`.

| Usuário | Como entra | Chamados |
|---|---|---|
| `onias85+cand-ti-<d>@gmail.com` | logado | 1 crítica (`makeCriticism`, 3) e 1 bug (`reportBug`, 1) |
| `onias85+cand-op-<d>@gmail.com` | logado | 1 dúvida (`clarifyDoubts`, 2) e 1 sugestão (`makeSuggestion`, 5) |
| `rec-<d>@betaconsult.onias.site` | sem login, e-mail digitado no painel | 1 elogio (`makeCompliment`, 6) |
| `onias85+ignorado-<d>@gmail.com` | sem login, conta descartável | 1 comentário (`makeComment`, 6), depois 1 bug |

- [ ] F.1 Envie na ordem inversa da prioridade (elogio primeiro, bug por último). Cada envio dá o toast, grava em `js_contact_us`, avisa o tópico certo do grupo "Jn - Fale Conosco" e manda ao usuário o e-mail de recebimento, com remetente `curriculos@onias.site`.
- [ ] F.2 Segundo envio de um tipo com cota, pela mesma conta: 429. **Não** libere a cota.
- [ ] F.3 O operador manda `/ticketsPendentes`. Esperado: o bug primeiro, depois dúvida, crítica, sugestão e, por último, elogio e comentário (mesma prioridade, por data). Os dados de cada usuário aparecem no ticket certo.
- [ ] F.4 O operador responde cada um (`responder <texto>`), com um texto que diga de quem é o ticket. Esperado: cada endereço recebe **só** a sua resposta, e o registro passa para `js_contact_us_solved` com `supportResponse`.
- [ ] F.5 Tela **Meus chamados** de cand-ti e cand-op: "Respondido" com a resposta certa; a de cada um não mostra o chamado do outro.
- [ ] F.6 O operador ignora `ignorado-<d>`. O bug dele dá 403 `userNotAllowed`. Desfaça no fim e confira que um novo envio passa.
- [ ] F.7 Depois de responder tudo, a fila diz "Você não tem tickets para resolver." Se houver tickets reais de usuários na fila, o operador **não** os responde: anote quantos eram antes e confira que continuam lá.
- [ ] F.8 Cota de 24 h (D2, corrigido): no dia seguinte, a mesma conta envia de novo o tipo do F.2 e passa.
- [ ] F.9 Entrega: os e-mails de recebimento e de resposta chegam à **Caixa de entrada** dos aliases do Gmail, não ao Spam (remetente `curriculos@onias.site`, domínio autenticado no SendGrid). Os que passam pelo pega-tudo de um subdomínio podem cair no Spam por causa do redirecionamento; isso não conta como defeito.

## L — Planilha de limpeza

Cada linha: entidade, id (ou e-mail e LinkedIn), quando foi criado e por qual cenário. No fim:
- **Candidatos:** excluir o currículo pela tela (Excluir). Isso tira o currículo de `vis_resume`, `vis_resume_linkedin` e dos grupos. Depois, apagar pelo túnel as linhas de login (`js_login_*`, `jn_login_*`) e os grupos de acesso no `jn_grouper`/`jn_inactive_grouper` do e-mail.
- **Recrutadores** (os 5 de teste, nunca `curriculos@onias.site`): apagar de `vis_recruiter`/`vis_inactive_recruiter` e as visualizações em `vis_viewed_resume`. Apagar também a lista `vis_recruiter_resumes`, os contadores do Quem me viu dos candidatos de teste e o domínio dos recrutadores no `jn_grouper` (`alfatech.onias.site` e `betaconsult.onias.site` entram na busca de empresas).
- **Tickets:** responder (sai de `js_contact_us` para `js_contact_us_solved`) e então apagar da gêmea; desfazer o ignorado.
- **Sugestões:** rejeitadas ficam em `vis_skill_reviewed` (sem e-mail); apagar a linha da habilidade inventada.
- **Cotas e descartáveis:** `jn_ticket_daily_limit` e as cópias em `jn_disposable_record` dos e-mails de teste.
- **Supressões do SendGrid:** se algum endereço de teste cair em bounce, ele entra em `jn_email_suppressed`; apagar a linha e tirá-lo da lista de supressão no SendGrid.
- **Já anotado (2026-11-04):** `js_contact_us`/`js_contact_us_solved` de `onias852bfale-20261104@gmail.com` (lixo do defeito do `+`, ainda pendente na fila do bot), `onias85+fale-20261104@gmail.com` e `onias85+fale2-20261104@gmail.com`, com as cotas e as cópias descartáveis desses e-mails.

Antes de cada `_delete_by_query`, rodar a mesma consulta com `_count` e comparar com a planilha. Uma diferença para um lado ou para o outro bloqueia a exclusão. Os subdomínios e o pega-tudo podem ficar para a próxima campanha.
