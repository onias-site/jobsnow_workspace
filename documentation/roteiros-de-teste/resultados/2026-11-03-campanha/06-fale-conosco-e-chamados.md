# Roteiro 06 — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

Contas: `roteiro01b.20261103@teste.com` (logada), `roteiro06b.20261103@teste.com` (sem login, e-mail digitado no painel) e `roteiro06c.20261103@teste.com` (só digitado no modal de login). Operador pelo `automacao/SupportBotCommand.java`. Cotas liberadas antes com `automacao/libera-cota.ps1`.

**Prioridades atuais** (subiram 1 com o `/solveStackTrace`, que tem a 0): `reportBug` 1, `clarifyDoubts` 2, `makeCriticism` 3, `makeSuggestion` 5, `makeCompliment` e `makeComment` 6. O roteiro ainda mostra a tabela antiga (0, 1, 2, 4, 5, 5).

| Cenário | Resultado | Observação |
|---|---|---|
| F1 validações | ok | 1.1 "Responderemos para", 6 tipos, sem pré-escolha; 1.2 a 1.5 mensagens e `maxLength` 50/500; 1.6 422 `stringMinLength` e `stringAllowedValues`, 400 com e-mail inválido |
| F2 envio logado e cotas | ok | 2.1 toast, `js_contact_us`, e-mail e inbox com prioridade 3; 2.2 429; 2.3 o Cancelar limpa (Esc não repetido); 2.4 dúvida passa e a segunda dá 429; 2.5 dois bugs: um registro e um comando no inbox |
| F3 sem login | ok | 3.1 campo "Seu e-mail"; 3.2 `naoeumemail` barrado pelo navegador e elogio enviado; 3.3 ver a nota abaixo; 3.4 `stackTrace` gravado e mostrado ao operador |
| F4 tela de chamados | ok | "1 chamado" e "Em análise"; "Nenhum chamado deste tipo."; o combo traz também as associações e dissociações de hierarquia e a sugestão de habilidade |
| F5 operador | ok | 5.1 bugs primeiro; 5.2 e 5.3; 5.4 `js_contact_us_solved` com `supportResponse` e e-mail `JsNotifyUserAboutAnsweredContactUs`; 5.5 "Respondido" com a resposta; 5.6 "continua aberto" e a lista; 5.7 "Não há ticket aberto..." |
| F6 ignorar e voltar | ok | 6.1 e 6.2 (talvez/não); 6.3 tickets descartados (o elogio também); 6.4 403 `userNotAllowed` pela API; 6.5 `/ignoredContactUs` → "1" → volta a atender e o bug seguinte passa |

**Notas:**
1. **3.3:** o e-mail digitado no modal de login só chega ao painel enquanto o modal está aberto. Fechar o modal (X) chama `hideModal`, que limpa o e-mail, e aí o painel volta a pedir "Seu e-mail". O roteiro deve dizer "com o modal ainda aberto, clique em Fale Conosco".
2. **6.3:** logo depois do "sim", o elogio do usuário ignorado continuava em `jb_pending_tickets`, porque o `/pendingTickets` já o tinha movido. Não é defeito: o cancelamento fica em `jn_support_cancelled_command` e é aplicado na listagem seguinte, que mostrou só os tickets restantes e apagou o registro.
3. Sem stack trace, o bot mostra a linha "Stack trace:" vazia. É só aparência.
4. No fim, todos os tickets foram respondidos: "Você não tem tickets para resolver."
