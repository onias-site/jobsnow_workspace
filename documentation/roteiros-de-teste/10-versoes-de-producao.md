# Roteiro 10 — Versões de produção dos roteiros 01 a 09

**Pré-requisito:** deploy em dia (`/ccp-deploy` e `07-publicar-na-vm.ps1`), `scripts/checar-producao.py` limpo e o túnel do ES de produção aberto só para conferir e apagar (`gcloud compute ssh ... --tunnel-through-iap -- -L 9210:localhost:9200 -N`).

> **Criado em 2026-11-03.** Ainda não executado.

## Regras invioláveis

1. **Nunca** resetar a base de produção, nem rodar `CcpCreateEntities` contra ela.
2. Toda conta, currículo, ticket e recrutador criado pelo teste vai para a **planilha de limpeza** (seção L). No fim, apaga-se só o que está nela.
3. Os candidatos fictícios usam só skills, cargos, pretensões e DDD que existem em currículos reais. Nada de identificador real: e-mail, LinkedIn e nome são inventados.
4. Simulação de carga e estresse **só no local**.
5. O convite aos candidatos legados (`executaConviteDeCurriculos.bat`) **não** é testado em produção.
6. Nenhum segredo de `C:\segredos\producao.json` ou de `application_properties` aparece em saída, arquivo ou chat.
7. Defeito achado: corrigir o código, fazer o deploy, passar os dados com um script numerado em `documentation/deploy` (idempotente, pelo túnel) e **testar de novo o mesmo ponto** antes de seguir.

## O que muda em relação ao local

| Item | Local | Produção |
|---|---|---|
| Front | `http://localhost:3000` | `https://onias.site` |
| API vis / js | `localhost:8081` / `localhost:8082` | `https://api.onias.site` / `https://login.onias.site` |
| E-mail | mock em `C:\logs\email` | SendGrid real para os aliases `onias85+<papel>@gmail.com`, lidos pelo MCP do Gmail ou no Chrome |
| Operador do suporte | `automacao/SupportBotCommand.java` | Telegram real, bot `@onias_site_support_prd_bot`, pelo webhook `https://login.onias.site/telegram-webhook/support`: o operador digita no Telegram, ou a automação posta o update com o segredo do webhook, lido do arquivo sem exibi-lo |
| Cota diária | `automacao/libera-cota.ps1` | **não liberar**: cada cenário com cota usa uma conta nova |
| Sessão | aberta pela API em `localhost` | aberta pelo próprio modal, no Chrome, com o token do e-mail |
| Mês | — | o Mês/ano das telas abre no mês anterior; escolha o corrente |

## Contas (aliases)

| Papel | Alias |
|---|---|
| Candidato TI | `onias85+cand-ti-<d>@gmail.com` |
| Candidato operacional | `onias85+cand-op-<d>@gmail.com` |
| Candidato com LinkedIn emprestado | `onias85+cand-lk-<d>@gmail.com` |
| Recrutador freelancer (gmail) | `onias85+rec-free1-<d>@gmail.com`, `onias85+rec-free2-<d>@gmail.com` |

> **Limite dos aliases:** todo `onias85+...@gmail.com` é do domínio `gmail.com`, então em produção todos os recrutadores contam como `freelancer`. Os casos "mesmo domínio" e "outro domínio" do roteiro 09 só podem ser vistos no local, ou com caixas reais de outros domínios que o usuário tenha (por exemplo, `curriculos@onias.site`, que já é recrutador).

## Roteiro a roteiro

| Roteiro | Em produção | Ajustes |
|---|---|---|
| 01 Sugerir habilidade | sim | o operador **rejeita** tudo (ou desiste) para não criar habilidades reais; S8 (decisão vale para todos) só com rejeição; uma conta nova por envio, por causa da cota |
| 02 Ajuste de hierarquia | sim | o operador **rejeita tudo**: uma aprovação muda a taxonomia real |
| 03 Login | sim, pela tela | sem `03-modal-de-login.mjs` (ele fala com localhost); bloqueio e desbloqueio com o operador real; tokens no Gmail |
| 04 e 05 Tela do currículo | sim | currículos montados com dados reais anonimizados; C6 avisa o operador real |
| 06 Fale conosco | sim | todo ticket começa o título com `[TESTE <d>]`; o operador responde só a esses; F6 (ignorar) com uma conta descartável e desfeito no fim |
| 07 Acessos | sim | — |
| 08 e 09 E-mail aos recrutadores | sim, com cuidado | o processo agendado **não** está instalado; o envio é o `SendResumesToRecruiters.java` apontado para produção **só com os recrutadores de teste** nos argumentos (ele grava e envia só para eles); os links levam a `https://onias.site` |

## L — Planilha de limpeza

Cada linha: entidade, id (ou e-mail e LinkedIn), quando foi criado e por qual cenário. No fim:
- **Candidatos:** excluir o currículo pela tela (Excluir). Isso tira o currículo de `vis_resume`, `vis_resume_linkedin` e dos grupos. Depois, apagar pelo túnel as linhas de login (`js_login_*`, `jn_login_*`) e os grupos de acesso no `jn_grouper`/`jn_inactive_grouper` do e-mail.
- **Recrutadores:** apagar de `vis_recruiter`/`vis_inactive_recruiter`, as visualizações em `vis_viewed_resume`, a lista `vis_recruiter_resumes` e os contadores do Quem me viu dos candidatos de teste.
- **Tickets:** responder (sai de `js_contact_us` para `js_contact_us_solved`) e então apagar da gêmea; desfazer o ignorado em `/ignoredContactUs`.
- **Sugestões:** rejeitadas ficam em `vis_skill_reviewed` (sem e-mail); apagar a linha da habilidade inventada.
- **Cotas e descartáveis:** `jn_ticket_daily_limit` e as cópias em `jn_disposable_record` dos e-mails de teste.

Antes de cada `_delete_by_query`, rodar a mesma consulta com `_count` e comparar com a planilha. Uma diferença para um lado ou para o outro bloqueia a exclusão.
