# Roteiro 06 — Fale Conosco e Chamados

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, API js na 8082 e login), com as cotas do dia liberadas (item 5A).

> **Criado e executado em 2026-10-26**, no Chrome (modal e tela de chamados), pela API (`curl`) e pelo bot do suporte (`SupportBotCommand.java`). Contas: `roteiro03.20261026@teste.com` (logada), `roteiro06.20261026@teste.com` (só API) e `roteiro06b.20261026@teste.com` (sem login, e-mail digitado). Tudo conferiu; notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

## Como funciona (resumo)

1. O botão **Fale Conosco** fica no canto inferior direito de todas as páginas do layout padrão. Abre um painel com o e-mail, o tipo, o título e a mensagem; o **X**, o **Cancelar** e a tecla **Esc** limpam e fecham.
2. **Não exige sessão** (o defeito pode ser a própria tela de login). O e-mail é o do login; sem login, o que estiver digitado no modal de login; sem nenhum dos dois, o painel mostra o campo "Seu e-mail". Com e-mail conhecido, o painel diz "Responderemos para {email}".
3. Envio: `POST localhost:8082/contact-us/{email}` (e-mail cru no caminho), corpo `{type, title, description, stackTrace?}`. O `stackTrace` é o último erro de JavaScript não tratado da aba.
4. Tipos (`JsContactUsTypes`) e prioridade no `/pendingTickets`:

   | Tipo (`type`) | No combo | Prioridade | Cota diária |
   |---|---|---|---|
   | `reportBug` | Reportar um bug | 0 | nenhuma |
   | `clarifyDoubts` | Esclarecer dúvidas | 1 | própria (1 por dia) |
   | `makeCriticism` | Fazer uma crítica | 2 | compartilhada |
   | `makeSuggestion` | Fazer uma sugestão | 4 | compartilhada |
   | `makeCompliment` | Fazer um elogio | 5 | compartilhada |
   | `makeComment` | Fazer um comentário | 5 | compartilhada |

   A cota compartilhada (`jn_ticket_daily_limit`, `quotaGroup: sharedTickets`) vale 1 por dia somando fale conosco, sugestão de habilidade e ajuste de hierarquia.
5. Um ticket aberto por e-mail e tipo (PK email + type em `js_contact_us`): um novo do mesmo tipo substitui o aberto, e o comando no inbox do suporte não se repete.
6. Ao salvar: e-mail "Recebemos a sua mensagem do fale conosco" ao usuário (`C:\logs\email\<email>\com.js.messages.JsNotifySupportAndUserAboutContactUs.html`) e `/answerContactUs <type> <email>` no inbox do suporte (`jn_support_pending_command`, com a prioridade).
7. O operador responde com `/answerContactUs <type> <email>`:
   - `responder <texto>` (10 a 500 caracteres): o ticket vai para a gêmea `js_contact_us_solved` com `supportResponse` e o usuário recebe "O seu ticket do fale conosco foi respondido".
   - `próximo`: o ticket continua aberto e o bot mostra a lista de pendentes.
   - `ignorar` → `sim`: o usuário passa a ser ignorado em todos os comandos (`JnEntityCommandNotAllowedToUser`); os tickets abertos dele e os comandos no inbox são descartados; novos envios dão 403. `/ignoredContactUs` lista os ignorados e volta a atendê-los.
8. A tela **Meus dados → Chamados** (`/meus-dados/chamados`) lê os tickets do usuário logado, por tipo, de `GET localhost:8082/grouper/{email}/jn_login_email/<entidade>/<parentId>/bothSides`: os do `jn_grouper` aparecem "Em análise"; os do `jn_inactive_grouper`, com a situação final ("Respondido" no fale conosco). O combo traz também as associações e dissociações de hierarquia e as sugestões de habilidade (roteiros 01 e 02).

---

## F1 — Validações do painel

- [ ] 1.1 Logado, abra **Fale Conosco**. Esperado: "Responderemos para {email}", sem campo de e-mail; combo com os 6 tipos, sem opção pré-escolhida.
- [ ] 1.2 **Enviar** com tudo vazio → "Escolha o tipo da mensagem."
- [ ] 1.3 Escolha "Fazer uma crítica", título `Abc` → "O título precisa ter de 5 a 50 caracteres."
- [ ] 1.4 Título válido, mensagem `curta` → "A mensagem precisa ter de 10 a 500 caracteres."
- [ ] 1.5 O título não aceita mais de 50 caracteres e a mensagem, mais de 500 (`maxLength`).
- [ ] 1.6 Pela API, os mesmos limites dão 422 (`stringMinLength` em `title`/`description`; tipo fora da lista dá `stringAllowedValues`); e-mail inválido no caminho dá 400.

## F2 — Envio logado e cotas

- [ ] 2.1 Envie a crítica com uma mensagem válida. Esperado: toast "Mensagem enviada! — Enviamos para {email} um e-mail com os detalhes; o ticket está em análise.", painel fechado e limpo; registro em `js_contact_us` (e-mail em SHA-1); e-mail "Recebemos a sua mensagem do fale conosco"; `/answerContactUs makeCriticism {email}` no inbox com prioridade 2.
- [ ] 2.2 Tente uma sugestão no mesmo dia. Esperado: "Você já abriu um ticket nas últimas 24 horas (fale conosco, sugestão de habilidade ou ajuste de hierarquia). Um novo poderá ser aberto quando completar 24 horas do envio anterior; bugs podem ser reportados a qualquer momento." (429).
- [ ] 2.3 **Esc** fecha o painel; ao reabrir, os campos estão vazios.
- [ ] 2.4 Envie uma dúvida: passa (cota própria). Uma segunda dúvida → "Você já enviou uma dúvida nas últimas 24 horas. Aguarde a resposta ou envie outra quando completar 24 horas do envio anterior." (429).
- [ ] 2.5 Envie dois bugs seguidos. Esperado: os dois passam; em `js_contact_us` fica só o segundo (mesmo e-mail e tipo) e o inbox tem um único `/answerContactUs reportBug {email}`.

## F3 — Envio sem login

- [ ] 3.1 Em outra aba, `sessionStorage.removeItem('login')` e abra `/meus-dados/chamados`. Abra **Fale Conosco**. Esperado: campo "Seu e-mail".
- [ ] 3.2 E-mail `naoeumemail` → o navegador barra o envio (campo `type=email`). Com um e-mail válido, um elogio → toast "Mensagem enviada!" com o e-mail digitado; inbox com prioridade 5.
- [ ] 3.3 Escolha um tipo na tela de chamados → "Entre com o seu e-mail para ver os seus chamados." e o modal de login. Digite um e-mail no modal e abra **Fale Conosco**: "Responderemos para" o e-mail digitado.
- [ ] 3.4 Provoque um erro na aba (console: `setTimeout(() => { function quebraNoRoteiro06(){ throw new Error('erro proposital do roteiro 06'); } quebraNoRoteiro06(); })`) e reporte um bug. Esperado: o ticket mostrado ao operador traz o "Stack trace: Error: erro proposital do roteiro 06 ...".

## F4 — Tela de chamados

- [ ] 4.1 Logado, em **Chamados**, escolha cada tipo enviado. Esperado: "1 chamado", colunas Data, Situação, Título, Mensagem e Resposta do suporte, situação "Em análise" e resposta "—".
- [ ] 4.2 Um tipo sem envio → "Nenhum chamado deste tipo."

## F5 — Operador do suporte

- [ ] 5.1 `/pendingTickets`. Esperado: os bugs (prioridade 0) primeiro, depois os de prioridade 1 (dúvidas e `/solveLoginTokenTicket`), e assim por diante; `2` anda para o próximo.
- [ ] 5.2 `/answerContactUs reportBug {email}`. Esperado: "Fale conosco de {email}", tipo, título, descrição, stack trace e as opções.
- [ ] 5.3 Resposta sem opção (`curto`) → "Não entendi a resposta. A resposta ao usuário precisa ter de 10 a 500 caracteres." e as opções de novo.
- [ ] 5.4 `responder <texto>` → "O ticket (Reportar um bug) de {email} foi respondido. O usuário receberá a resposta por e-mail."; o ticket sai de `js_contact_us` e vai para `js_contact_us_solved` com `supportResponse`; e-mail "O seu ticket do fale conosco foi respondido" com a resposta; o comando sai do inbox.
- [ ] 5.5 Recarregue a tela de chamados e escolha "Reportar um bug". Esperado: situação **Respondido** e a resposta do suporte.
- [ ] 5.6 `/answerContactUs clarifyDoubts {email}` → `próximo`. Esperado: "O ticket (Esclarecer dúvidas) de {email} continua aberto." e a lista de pendentes; a tela continua mostrando "Em análise".
- [ ] 5.7 `/answerContactUs makeCompliment {email}` sem ticket desse tipo → "Não há ticket aberto do fale conosco do tipo 'makeCompliment' para o e-mail '{email}'".

## F6 — Ignorar e voltar a atender

- [ ] 6.1 `/answerContactUs clarifyDoubts {email2}` → `ignorar`. Esperado: "Confirma que o usuário {email2} será ignorado pelo suporte, em todos os comandos? ... Responda: sim ou não".
- [ ] 6.2 `talvez` → "Não entendi a resposta." e a pergunta de novo; `não` → "O usuário não será ignorado." e as opções.
- [ ] 6.3 `ignorar` → `sim`. Esperado: "O usuário {email2} foi ignorado pelo suporte, em todos os comandos. Os tickets abertos dele foram descartados."; nada de {email2} em `js_contact_us` nem no inbox.
- [ ] 6.4 Novo envio de {email2}, mesmo um bug → 403; na tela: "O suporte não está aceitando novas mensagens deste e-mail."
- [ ] 6.5 `/ignoredContactUs` → "O suporte está ignorando 1 usuário", "Usuário 1 de 1 => {email2}", "Ignorado no comando answerContactUs (<título>)". `1` → "Voltando a atender o usuário {email2}" e "... não é mais ignorado pelo suporte ...". Um novo bug de {email2} passa (200).

## Observações da execução (2026-10-26)

| # | O que se viu | Situação |
|---|---|---|
| 1 | A resposta 200 do `POST /contact-us/{email}` devolvia `ip`, `userAgent` e `sessionToken` (vazio), como as sugestões de habilidade e hierarquia e as recusas do login. | **Corrigido em 2026-10-26** (`CcpRestApiSessionValuesRemoverSpring`, central nas duas APIs) |
| 2 | A tela de chamados guarda as respostas por tipo até recarregar a página (`doACachedRequest`): um ticket respondido ou enviado com a tela aberta só muda depois do F5. | **a avaliar** |
| 3 | A cota vale 24 horas contadas do envio (a cópia em `jn_disposable_record` expira 24 horas depois), mas as mensagens falavam em "hoje" e "amanhã". | **Corrigido em 2026-10-26** (textos do fale conosco e dos modais de sugestão explicam as 24 horas e a cota dividida) |
| 4 | E-mail inválido no painel sem login é barrado pelo próprio navegador (`type=email`), antes da mensagem "Informe um e-mail válido." do painel. | ok |
| 5 | O `/pendingTickets` tinha 44 tickets acumulados de execuções anteriores; a ordem por prioridade conferiu. | ok |
| 6 | F1 a F6 conferidos: tela, API, ES (`js_contact_us`, `js_contact_us_solved`, `jn_support_pending_command`), e-mails e bot. | ok |
