# Roteiro 08 — E-mail de currículos ao recrutador, Quem me viu e telas do recrutador

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4, um currículo ativo salvo nos últimos 7 dias pela tela (roteiro 04) com uma conta que tenha senha, e `recruiterLinksSecret` na variável de ambiente `application_properties` (sem ele os links não são assinados).

> **Criado e executado em 2026-10-26**, no Chrome, com o currículo de TI de `roteiro03.20261026@teste.com` e três recrutadores: `recrutador08.20261026@empresa08.com.br` (profissional), `recrutador08.20261026@gmail.com` (freelancer) e a própria `roteiro03.20261026@teste.com` (para as telas que exigem login). Tudo conferiu; notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

## Como funciona (resumo)

1. O processo `VisBusinessSendResumesToRecruiters` (agendado de segunda a sexta, ainda fora desta máquina) manda a cada recrutador de `vis_recruiter` uma tabela com os currículos inseridos ou alterados nos últimos 7 dias (os 40 primeiros no e-mail; a lista inteira fica em `vis_recruiter_resumes`, lida pela tela **Currículos da semana**). Cada linha tem o link **Ver currículo**, e o rodapé, o de descadastro. Os links são assinados: `token = sha1(<finalidade>|<valores>|<segredo>)`.
2. **Ver currículo** (`/recrutador/ver-curriculo?email=&resume=&token=`, sem login): pede confirmação ("Deseja abrir este currículo?"), porque os robôs dos provedores de e-mail clicam em todos os links. Confirmado: `POST localhost:8081/recruiter-email-link/view-resume` grava a visualização (`vis_viewed_resume`), abre o LinkedIn numa aba nova e mostra o apelido sugerido, que o recrutador pode trocar (`/recruiter-email-link/alias`, de 5 a 200 caracteres).
3. Cada visualização alimenta:
   - **Quem me viu** do dono do currículo (`/meus-dados/quem-me-viu`, `GET /resume/{email}/viewers/{yyyyMM}`): visualizações por domínio do recrutador no mês, **uma por recrutador por mês**; os domínios não profissionais (gmail etc.) contam todos sob `freelancer`;
   - **Currículos visualizados** do recrutador (`/meu-recrutamento/curriculos-visualizados`, `GET /recruiter/{email}/viewed-resumes/{yyyyMM}`): um item por currículo no mês, com apelido, LinkedIn legível e data; **ver detalhes** (`POST .../details` com `{linkedin}`) expande a linha no formato do e-mail.
4. **Descadastrar** (`/recrutador/descadastrar?email=&token=`, sem login): confirmação e `POST /recruiter-email-link/unsubscribe`, que move o recrutador para `vis_inactive_recruiter`; repetir dá a mesma resposta.

## Automação

| Arquivo | Para quê |
|---|---|
| `automacao/SendResumesToRecruiters.java` | faz o papel do agendador: grava os recrutadores dos argumentos em `vis_recruiter` (fonte "roteiro") e roda o processo só para eles; os e-mails vão para `C:\logs\email\<recrutador>\com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes.html` |

```bash
curl -XPOST "localhost:9200/jn_versionable,vis_resume,vis_recruiter,vis_viewed_resume/_refresh"
cd ccp_rest-api-tests_jobsnow
java @target/create-entities-args.txt ../documentation/roteiros-de-teste/automacao/SendResumesToRecruiters.java \
  recrutador08.20261026@empresa08.com.br recrutador08.20261026@gmail.com roteiro03.20261026@teste.com
```

Saída esperada: `OK {"emailsSent":3, "recruiters":[...], "resumesFound":N}`. Os links estão nos `href` do e-mail (troque `&amp;` por `&`). O mesmo recrutador não recebe um segundo e-mail no mesmo dia (`jn_email_message_sent`, diário por e-mail e assunto). Gravar o recrutador de novo o reativa: não passe um recrutador descadastrado se quiser mantê-lo fora.

---

## R1 — O e-mail

- [ ] 1.1 Rode a automação. Esperado: um e-mail por recrutador, assunto "Currículos inseridos ou alterados nos últimos 7 dias", colunas "O que importa", "Idiomas e habilidades", "Função / papel / emprego / ocupação", "Outras Informações" e "Datas e visualização"; em cada linha "Sua última visualização: nunca" e **Ver currículo**; no rodapé, o link de descadastro.

## R2 — Ver currículo (sem login)

> Para não abrir o LinkedIn de verdade, rode `window.open = () => null` no console antes de confirmar.

- [ ] 2.1 Abra o link com o `token` alterado → "Sim, abrir" → "Este link não é válido. Abra o currículo pelo link do e-mail que você recebeu."
- [ ] 2.2 Abra o link certo → "Não" → "O currículo não foi aberto. Para abri-lo, clique de novo no link do e-mail."
- [ ] 2.3 Abra de novo → "Sim, abrir". Esperado: "O currículo foi aberto numa nova aba. Dê a ele um apelido ...", campo com o apelido sugerido (idiomas, habilidades, pretensões, regiões e anos, unidos por `_`) e "De 5 a 200 caracteres (N usados)."
- [ ] 2.4 Apelido `Dev` → **Salvar visualização** desabilitado; `Dev Java do roteiro 08` → "Visualização salva. Nos próximos e-mails este currículo aparecerá com o apelido que você deu."; `vis_viewed_resume` com o apelido.
- [ ] 2.5 Repita o 2.3 com o link do recrutador gmail e com o da conta logada (sem salvar apelido).
- [ ] 2.6 Reabra o link do 2.4. Esperado: o campo já vem com "Dev Java do roteiro 08".

## R3 — Quem me viu (dono do currículo)

- [ ] 3.1 Logado com o dono, **Meus dados → Quem me viu**. Esperado: campo Mês/ano no mês corrente (máximo: o mês corrente), "3 visualizações no mês" e a grade Nome da consultoria × Visualizações: `empresa08.com.br 1`, `freelancer 1`, `teste.com 1`.
- [ ] 3.2 Depois do 2.6 (o mesmo recrutador de novo), recarregue. Esperado: os mesmos números (uma por recrutador por mês).
- [ ] 3.3 Mês anterior → "Nenhum recrutador viu o seu currículo neste mês." Limpar o campo volta ao mês corrente.

## R4 — Telas do recrutador logado

- [ ] 4.1 **Meu Recrutamento → Currículos visualizados**. Esperado: "1 currículo visualizado no mês", colunas Apelido, LinkedIn (legível) e Última visualização; **ver detalhes** expande a linha com as colunas do e-mail.
- [ ] 4.2 **Meu Recrutamento → Currículos da semana**. Esperado: "N currículos inseridos ou alterados nos últimos 7 dias", as mesmas colunas do e-mail e um **Ver currículo** por linha. A lista é a do momento do envio do e-mail: as visualizações feitas depois não mudam a coluna "Sua última visualização".

## R5 — Descadastrar (sem login)

- [ ] 5.1 Link com o `token` alterado → "Sim, descadastrar" → "Este link não é válido. Use o link do e-mail que você recebeu."
- [ ] 5.2 Link certo → diálogo "Não receber mais o e-mail de currículos — Deseja mesmo deixar de receber o e-mail de currículos em {email}?" → "Não" → "Nada mudou: você continuará recebendo o e-mail de currículos."
- [ ] 5.3 De novo → "Sim, descadastrar" → "Pronto: você não receberá mais o e-mail de currículos."; o recrutador sai de `vis_recruiter` e vai para `vis_inactive_recruiter`.
- [ ] 5.4 Recarregue e confirme de novo: a mesma mensagem.

## Observações da execução (2026-10-26)

| # | O que se viu | Situação |
|---|---|---|
| 1 | R1 a R5 conferidos na tela e no ES (`vis_viewed_resume` com o apelido, `vis_inactive_recruiter` com o descadastrado); a contagem do Quem me viu não subiu na segunda visualização do mesmo recrutador. | ok |
| 2 | Rodar o processo de novo no mesmo dia conta `emailsSent: 1`, mas o e-mail não sai (registro diário de `jn_email_message_sent` por e-mail e assunto); a confirmação do fale conosco, por outro lado, saiu a cada ticket do mesmo dia. | não se aplica: o processo não é reprocessado; se for, limpam-se os índices que o travarem |
| 3 | Os links do e-mail apontam para `http://localhost:3000` (o `frontendUrl` local). | ambiente |
| 4 | O processo ainda não está agendado em lugar nenhum (débito conhecido). | pendente |
