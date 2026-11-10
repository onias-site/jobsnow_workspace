# Roteiro 06 — Fale Conosco e Chamados

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, API js na 8082 e login), com as cotas do dia liberadas (item 5A).

> **Criado e executado em 2026-10-26**, no Chrome (modal e tela de chamados), pela API (`curl`) e pelo bot do suporte (`SupportBotCommand.java`). Contas: `roteiro03.20261026@teste.com` (logada), `roteiro06.20261026@teste.com` (só API) e `roteiro06b.20261026@teste.com` (sem login, e-mail digitado). Tudo conferiu; notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

> **Executado de novo em 2026-11-03**. Resultado em [resultados/2026-11-03-campanha/06-fale-conosco-e-chamados.md](resultados/2026-11-03-campanha/06-fale-conosco-e-chamados.md). **Prioridades atuais** (subiram 1 com o `/solveStackTrace`): `reportBug` 1, `clarifyDoubts` 2, `makeCriticism` 3, `makeSuggestion` 5, `makeCompliment` e `makeComment` 6. **3.3:** clique em **Fale Conosco com o modal de login ainda aberto**, porque fechar o modal limpa o e-mail digitado.

> **Atualizado em 2026-11-07:** a crítica ganhou cota diária própria (`quotaGroup: makeCriticism`, como a dúvida) e deixou a compartilhada; todo envio passa por um diálogo **"Confirmar envio"**; e a tela guarda a cota de cada grupo no `localStorage` (`ticketDailyQuotas`, por e-mail), sem chamar o backend enquanto ela valer. Cenário F2 refeito. **Antes do F2**, libere o dia (item 5A da preparação) e rode `localStorage.removeItem('ticketDailyQuotas')` no Console da tela.
>
> **Atualizado em 2026-11-07 (2):** na tela de chamados, célula com mais de 120 caracteres ou 3 linhas mostra o começo do texto com "…" e o link **ver tudo**, que abre um modal com o texto inteiro. Cenários 4.3 a 4.6.
>
> **Atualizado em 2026-11-09:** na tela de chamados, (1) o combo nomeia o tipo do chamado já aberto ("Bug", "Elogio", "Crítica", "Sugestão", "Comentário", "Dúvida"), e não a ação de abrir um ("Reportar um bug"...), que continua só no painel do Fale Conosco; (2) fechar o modal de login sem entrar leva à tela inicial; (3) a grade é paginada, 10 chamados por página. Cenários 3.5, 4.0, 4.7 e 5.5.

## Como funciona (resumo)

1. O botão **Fale Conosco** fica no canto inferior direito de todas as páginas do layout padrão. Abre um painel com o e-mail, o tipo, o título e a mensagem; o **X**, o **Cancelar** e a tecla **Esc** limpam e fecham.
2. **Não exige sessão** (o defeito pode ser a própria tela de login). O e-mail é o do login; sem login, o que estiver digitado no modal de login; sem nenhum dos dois, o painel mostra o campo "Seu e-mail". Com e-mail conhecido, o painel diz "Responderemos para {email}".
3. Envio: `POST localhost:8082/contact-us/{email}` (e-mail cru no caminho), corpo `{type, title, description, stackTrace?}`. O `stackTrace` é o último erro de JavaScript não tratado da aba.
4. Tipos (`JsContactUsTypes`) e prioridade no `/pendingTickets`:

   | Tipo (`type`) | No combo | Prioridade | Cota diária |
   |---|---|---|---|
   | `reportBug` | Reportar um bug | 0 | nenhuma |
   | `clarifyDoubts` | Esclarecer dúvidas | 1 | própria (1 por dia) |
   | `makeCriticism` | Fazer uma crítica | 2 | própria (1 por dia, desde 2026-11-07) |
   | `makeSuggestion` | Fazer uma sugestão | 4 | compartilhada |
   | `makeCompliment` | Fazer um elogio | 5 | compartilhada |
   | `makeComment` | Fazer um comentário | 5 | compartilhada |

   A cota compartilhada (`jn_ticket_daily_limit`, `quotaGroup: sharedTickets`) vale 1 por dia somando fale conosco (exceto bug, dúvida e crítica), sugestão de habilidade e ajuste de hierarquia. A crítica tem a sua (`quotaGroup: makeCriticism`), como a dúvida (`clarifyDoubts`).

   **No navegador (desde 2026-11-07):** quando o backend aceita um chamado com cota, a tela grava em `localStorage.ticketDailyQuotas` o e-mail, o grupo e a hora; por 24 horas, um novo chamado do mesmo grupo é recusado no próprio painel ("Você já enviou ... Poderá enviar de novo a partir de dd/mm/aa hh:mm.") sem chamar o backend. O 429 continua existindo para a cota gasta em outro navegador, e não grava a marca. O bug não grava nada.

   **Confirmação (desde 2026-11-07):** depois das validações e da cota, **Enviar** abre o diálogo **"Confirmar envio"** (**Sim, enviar** / **Não**). Bug: só "Tem certeza de que deseja enviar este bug ao suporte?". Dúvida e crítica: avisam que só é possível enviar uma única por dia. Elogio, sugestão e comentário: avisam do chamado único por dia da cota compartilhada e listam os outros que ficarão bloqueados (por exemplo, no elogio: sugestão pelo fale conosco, comentário pelo fale conosco, sugestão de habilidade e ajuste de hierarquia de habilidades).
5. Um ticket aberto por e-mail e tipo (PK email + type em `js_contact_us`): um novo do mesmo tipo substitui o aberto, e o comando no inbox do suporte não se repete.
6. Ao salvar: e-mail "Recebemos a sua mensagem do fale conosco" ao usuário (`C:\logs\email\<email>\com.js.messages.JsNotifySupportAndUserAboutContactUs.html`) e `/answerContactUs <type> <email>` no inbox do suporte (`jn_support_pending_command`, com a prioridade).
7. O operador responde com `/answerContactUs <type> <email>`:
   - `responder <texto>` (10 a 500 caracteres): o ticket vai para a gêmea `js_contact_us_solved` com `supportResponse` e o usuário recebe "O seu ticket do fale conosco foi respondido".
   - `próximo`: o ticket continua aberto e o bot mostra a lista de pendentes.
   - `ignorar` → `sim`: o usuário passa a ser ignorado em todos os comandos (`JnEntityCommandNotAllowedToUser`); os tickets abertos dele e os comandos no inbox são descartados; novos envios dão 403. `/ignoredContactUs` lista os ignorados e volta a atendê-los.
8. A tela **Meus dados → Chamados** (`/meus-dados/chamados`) lê os tickets do usuário logado, por tipo, de `GET localhost:8082/grouper/{email}/jn_login_email/<entidade>/<parentId>/bothSides`: os do `jn_grouper` aparecem "Em análise"; os do `jn_inactive_grouper`, com a situação final ("Respondido" no fale conosco). O combo traz também as associações e dissociações de hierarquia e as sugestões de habilidade (roteiros 01 e 02). Desde 2026-11-09, as opções do combo dizem o tipo do chamado (Bug, Elogio, Crítica, Sugestão, Comentário, Dúvida, Associação de hierarquia, Dissociação de hierarquia, Sugestão de habilidade), para a tela não parecer servir para abrir chamados; a grade mostra 10 chamados por página, com o rodapé "1 a 10 de N" e os botões de página; sem login, fechar o modal sem entrar leva à tela inicial (`/`).

---

## F1 — Validações do painel

- [ ] 1.1 Logado, abra **Fale Conosco**. Esperado: "Responderemos para {email}", sem campo de e-mail; combo com os 6 tipos, sem opção pré-escolhida.
- [ ] 1.2 **Enviar** com tudo vazio → "Escolha o tipo da mensagem."
- [ ] 1.3 Escolha "Fazer uma crítica", título `Abc` → "O título precisa ter de 5 a 50 caracteres."
- [ ] 1.4 Título válido, mensagem `curta` → "A mensagem precisa ter de 10 a 500 caracteres."
- [ ] 1.5 O título não aceita mais de 50 caracteres e a mensagem, mais de 500 (`maxLength`).
- [ ] 1.6 Pela API, os mesmos limites dão 422 (`stringMinLength` em `title`/`description`; tipo fora da lista dá `stringAllowedValues`); e-mail inválido no caminho dá 400.

## F2 — Envio logado e cotas

- [ ] 2.1 Escolha "Fazer uma crítica", título e mensagem válidos → **Enviar**. Esperado: diálogo **"Confirmar envio"**: "Tem certeza de que deseja enviar esta crítica? Atenção: só é possível enviar uma única crítica por dia; depois deste envio, outra só poderá ser enviada daqui a 24 horas."
- [ ] 2.2 **Não** → o diálogo fecha, o painel continua preenchido e nada vai ao Network. Com o diálogo aberto, **Esc** fecha só o diálogo, sem limpar o painel.
- [ ] 2.3 **Enviar** → **Sim, enviar**. Esperado: toast "Mensagem enviada! — Enviamos para {email} um e-mail com os detalhes; o ticket está em análise.", painel fechado e limpo; registro em `js_contact_us` (e-mail em SHA-1); `jn_ticket_daily_limit` com `quotaGroup: makeCriticism`; `localStorage.getItem('ticketDailyQuotas')` com o e-mail e `makeCriticism`; e-mail "Recebemos a sua mensagem do fale conosco"; `/answerContactUs makeCriticism {email}` no inbox com prioridade 3.
- [ ] 2.4 Uma segunda crítica. Esperado: "Você já enviou uma crítica pelo fale conosco nas últimas 24 horas. Poderá enviar de novo a partir de dd/mm/aa hh:mm." no painel, sem diálogo e **nada no Network**.
- [ ] 2.5 A crítica não gasta a cota compartilhada: envie um elogio. Esperado: o diálogo lista "sugestão pelo fale conosco, comentário pelo fale conosco, sugestão de habilidade e ajuste de hierarquia de habilidades"; **Sim, enviar** → passa (200), e `jn_ticket_daily_limit` ganha `quotaGroup: sharedTickets`.
- [ ] 2.6 Uma sugestão pelo fale conosco. Esperado: "Você já enviou um chamado de sugestão de habilidade, ajuste de hierarquia ou fale conosco (exceto bug, dúvida e crítica) nas últimas 24 horas. Poderá enviar de novo a partir de ...", sem chamar o backend. O mesmo aviso aparece, em toast, na sugestão de habilidade e no ajuste de hierarquia (roteiros 01 e 02).
- [ ] 2.7 O 429 do backend: rode `localStorage.removeItem('ticketDailyQuotas')` no Console da tela e envie de novo a sugestão → **Sim, enviar**. Esperado: "Você já abriu um ticket nas últimas 24 horas (fale conosco, sugestão de habilidade ou ajuste de hierarquia). Um novo poderá ser aberto quando completar 24 horas do envio anterior; bugs podem ser reportados a qualquer momento." (429). Uma crítica nessas condições daria "Você já enviou uma crítica nas últimas 24 horas. Uma nova poderá ser enviada quando completar 24 horas do envio anterior." A marca não é gravada no 429.
- [ ] 2.8 **Esc** (sem diálogo) fecha o painel; ao reabrir, os campos estão vazios.
- [ ] 2.9 Envie uma dúvida: o diálogo avisa da "uma única dúvida por dia"; passa (cota própria). Uma segunda dúvida → "Você já enviou uma dúvida pelo fale conosco nas últimas 24 horas. Poderá enviar de novo a partir de ...", sem chamar o backend.
- [ ] 2.10 Envie dois bugs seguidos. Esperado: o diálogo só pergunta "Tem certeza de que deseja enviar este bug ao suporte?", sem falar de cota; os dois passam; em `js_contact_us` fica só o segundo (mesmo e-mail e tipo) e o inbox tem um único `/answerContactUs reportBug {email}`; `ticketDailyQuotas` não ganha nada de bug.

## F3 — Envio sem login

- [ ] 3.1 Numa **janela anônima** (desde 2026-11-09 as abas normais compartilham o login, e apagá-lo numa desloga todas), abra `/meus-dados/chamados`. Abra **Fale Conosco**. Esperado: campo "Seu e-mail".
- [ ] 3.2 E-mail `naoeumemail` → o navegador barra o envio (campo `type=email`). Com um e-mail válido, um elogio → diálogo de confirmação → **Sim, enviar** → toast "Mensagem enviada!" com o e-mail digitado; inbox com prioridade 6. A marca do `localStorage` fica com o e-mail digitado.
- [ ] 3.3 Escolha um tipo na tela de chamados → "Entre com o seu e-mail para ver os seus chamados." e o modal de login. Digite um e-mail no modal e abra **Fale Conosco**: "Responderemos para" o e-mail digitado.
- [ ] 3.4 Provoque um erro na aba (console: `setTimeout(() => { function quebraNoRoteiro06(){ throw new Error('erro proposital do roteiro 06'); } quebraNoRoteiro06(); })`) e reporte um bug. Esperado: o ticket mostrado ao operador traz o "Stack trace: Error: erro proposital do roteiro 06 ...".
- [ ] 3.5 **Fechar o modal sem entrar** (desde 2026-11-09): ainda sem login, recarregue `/meus-dados/chamados` e escolha um tipo. Esperado: o modal "Diga quem é você, antes de continuar..."; fechado sem entrar (pelo X ou pela tecla Esc), leva à tela inicial (`/`), em vez de deixar a tela de chamados vazia. Abra de novo, escolha um tipo e entre pelo modal: a tela continua em Chamados e carrega os chamados do tipo escolhido.

## F4 — Tela de chamados

- [ ] 4.0 **Rótulos do combo** (desde 2026-11-09): logado, abra **Chamados** e abra o combo "Tipo de chamado". Esperado, nesta ordem: Bug, Elogio, Crítica, Sugestão, Comentário, Dúvida, Associação de hierarquia, Dissociação de hierarquia, Sugestão de habilidade. Nenhuma opção começa por verbo ("Reportar", "Fazer", "Esclarecer"). O combo do painel **Fale Conosco** continua com os verbos (Reportar um bug, Fazer um elogio...).
- [ ] 4.1 Logado, em **Chamados**, escolha cada tipo enviado. Esperado: "1 chamado", colunas Data, Situação, Título, Mensagem e Resposta do suporte, situação "Em análise" e resposta "—".
- [ ] 4.2 Um tipo sem envio → "Nenhum chamado deste tipo."
- [ ] 4.3 **Texto comprido na grade** (desde 2026-11-07): envie um chamado com mensagem de mais de 120 caracteres (ou de 4 linhas ou mais, mesmo curtas) e outro com mensagem curta, de tipos diferentes; recarregue a tela e escolha o tipo do comprido. Esperado: a coluna **Mensagem** mostra o começo do texto (até 120 caracteres e 3 linhas, cortado no último espaço) terminando em "…" e o link **ver tudo**; o tipo da mensagem curta mostra o texto inteiro, sem link.
- [ ] 4.4 Clique em **ver tudo**. Esperado: modal com o título da coluna ("Mensagem") e o texto inteiro, com as quebras de linha; fecha pelo X, pelo Esc e clicando fora (a grade continua igual).
- [ ] 4.5 Depois do 5.4 com uma resposta de mais de 120 caracteres, a coluna **Resposta do suporte** do chamado respondido mostra o mesmo corte e o link **ver tudo**, e o modal tem o título "Resposta do suporte". O mesmo vale para a **Justificativa** e a **Resposta do suporte** dos tipos de hierarquia e de sugestão de habilidade (roteiros 01 e 02).
- [ ] 4.6 Celular (largura de 390 px): o link fica junto do texto cortado e o modal ocupa a largura da tela, sem rolagem horizontal da página.
- [ ] 4.7 **Paginação** (desde 2026-11-09): num tipo com chamados, abaixo da grade aparece "1 a N de N" (N até 10) e nenhum botão de página. Num tipo sem chamados, só "Nenhum chamado deste tipo.", sem rodapé. Com mais de 10 chamados de um tipo (difícil de produzir pela tela: as cotas e o mesmo e-mail e tipo sobrescrevem o fale conosco), o rodapé mostra "1 a 10 de N" e os botões de página; trocar de tipo volta à página 1. A divisão em páginas é coberta por `presentation/components/source/paginate.test.ts`.

## F5 — Operador do suporte

- [ ] 5.1 `/pendingTickets`. Esperado: os bugs (prioridade 0) primeiro, depois os de prioridade 1 (dúvidas e `/solveLoginTokenTicket`), e assim por diante; `2` anda para o próximo.
- [ ] 5.2 `/answerContactUs reportBug {email}`. Esperado: "Fale conosco de {email}", tipo, título, descrição, stack trace e as opções.
- [ ] 5.3 Resposta sem opção (`curto`) → "Não entendi a resposta. A resposta ao usuário precisa ter de 10 a 500 caracteres." e as opções de novo.
- [ ] 5.4 `responder <texto>` → "O ticket (Reportar um bug) de {email} foi respondido. O usuário receberá a resposta por e-mail."; o ticket sai de `js_contact_us` e vai para `js_contact_us_solved` com `supportResponse`; e-mail "O seu ticket do fale conosco foi respondido" com a resposta; o comando sai do inbox.
- [ ] 5.5 Recarregue a tela de chamados e escolha "Bug". Esperado: situação **Respondido** e a resposta do suporte.
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
