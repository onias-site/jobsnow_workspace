# Roteiro 07 — Acessos (histórico de login) e logout

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, API js na 8082) e uma conta com senha (por exemplo, a criada no roteiro 03).

> **Criado e executado em 2026-10-26**, no Chrome, com `roteiro03.20261026@teste.com`. Tudo conferiu; notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

> **Executado de novo em 2026-11-03** com `roteiro01b.20261103@teste.com`. Sem defeitos. No A3, o modal foi direto à senha. Resultado em [resultados/2026-11-03-campanha/07-acessos-e-logout.md](resultados/2026-11-03-campanha/07-acessos-e-logout.md).

> **Atualizado em 2026-11-09:** fechar o modal de login sem entrar leva à tela inicial (cenário 2.3), e a grade é paginada, 10 acessos por página (cenário 1.5).

> **Executado de novo em 2026-11-10** com `roteiro07a.20261109@teste.com` (13-14 acessos gerados pela API com 8 User-Agents, `scratchpad/r07-gen.mjs` da sessão) e `roteiro07b.20261109@teste.com` (1 acesso). Sem defeitos de sistema: Sessão atual/Expirou com as dicas, paginação (1 a 10 de 13, página 2 "11 a 13 de 13"; "1 a 1 de 1" sem botões), fechar o modal pelo X/Esc e depois de um 401 leva a `/`. O 1.4 (outro navegador de verdade) não foi feito.

## Como a tela funciona (resumo)

1. **Meus dados → Acessos** (`/meus-dados/acessos`; também no menu do usuário) lista os logins do usuário logado, do mais recente ao mais antigo: IP, navegador (User-Agent), data do login e data do logout.
2. Uma requisição só: `GET localhost:8082/grouper/{email}/jn_login_email/js_login_session_validation/<parentId>/bothSides`. Cada login grava `{userAgent, ip, loginDate}` no grupo do e-mail em `jn_grouper`; cada logout grava `{userAgent, ip, logoutDate}` no mesmo grupo em `jn_inactive_grouper`. A tela casa cada logout com o login mais recente do mesmo cliente (IP e navegador) ainda sem logout. O grupo guarda os 100 últimos de cada lado.
3. Login sem logout (desde 2026-11-07): a sessão deste navegador mostra **Sessão atual** em verde (dica: "A sessão aberta neste navegador"); os demais mostram **Expirou** em cinza (dica: "A sessão expirou sem logout"). Até 2026-11-07 todos mostravam "—". A sessão atual é o login mais recente sem logout feito com o mesmo navegador (User-Agent igual ao do navegador); ver `currentSessionIndex` em `accessesReconciliation.ts`.
4. Sem login (ou com a sessão inválida), a tela mostra "Entre com o seu e-mail para ver os seus acessos." e abre o modal de login; ao entrar, a busca se repete. Desde 2026-11-09, fechar o modal sem entrar (X ou Esc) leva à tela inicial (`/`).
5. **Sair do Sistema** (menu do usuário) faz `DELETE localhost:8082/login/{email}/{sessionToken}` e apaga o `login` do `localStorage` (até 2026-11-09, do `sessionStorage`). Como a sessão vale para todas as abas, as outras abas abertas também saem, sem recarregar, e voltam à home.
6. Desde 2026-11-09 a grade mostra 10 acessos por página, com o rodapé "1 a 10 de N" e, havendo mais de uma página, os botões de página (`GridPagination`). O título continua com o total ("N acessos").

---

## A1 — Lista

- [ ] 1.1 Logado, abra **Acessos**. Esperado: "N acessos", colunas IP, Navegador, Login e Logout; a primeira linha é a sessão atual (Logout **Sessão atual**, em verde).
- [ ] 1.2 Confira os pares login/logout de sessões anteriores: cada logout fica na linha do login de onde saiu; sessões que expiraram ou foram derrubadas por uma nova senha mostram **Expirou** (com uma sessão aberta, um login com senha dá 409 `loginConflict`; só salvar a senha com o token do e-mail substitui a sessão aberta, e esse salvamento também aparece como um acesso). Nenhuma linha fica com a coluna Logout vazia ou com "—".
- [ ] 1.3 Só uma linha mostra **Sessão atual**, mesmo quando há outros logins sem logout feitos com este navegador (esses mostram **Expirou**).
- [ ] 1.4 Logado com a mesma conta em outro navegador (ou no celular), abra **Acessos** lá. Esperado: lá a **Sessão atual** é o login desse navegador, e o login do primeiro navegador aparece como **Expirou**, mesmo ainda aberto.
  > **⚠ Atenção:** a tela não sabe qual login gravado é o da aba. Com dois logins no mesmo navegador (janela normal e janela anônima; desde 2026-11-09 duas abas normais compartilham um só login), o mais antigo também aparece como **Expirou**, mesmo ainda aberto.
- [ ] 1.5 **Paginação** (desde 2026-11-09), com uma conta de mais de 10 acessos (faça logins e logouts até passar de 10, ou use uma conta antiga). Esperado: o título com o total ("N acessos"); 10 linhas; abaixo da grade, "1 a 10 de N" e os botões de página. A página 2 mostra "11 a 20 de N" (ou até N) com os acessos seguintes, na mesma ordem; a **Sessão atual** aparece só na página 1, e as linhas da página 2 mostram a data do logout ou **Expirou**. Com 10 acessos ou menos, o rodapé mostra "1 a N de N" sem botões.

## A2 — Logout

- [ ] 2.1 Menu do usuário → **Sair do Sistema**. Esperado: `localStorage.getItem('login')` é `null` (até 2026-11-09 era o `sessionStorage.login`); o menu passa a mostrar **Entrar no sistema**. Com **Acessos** aberto também numa segunda aba, ela sai junto, sem recarregar: volta à home e o menu dela mostra **Entrar no sistema**.
  > **Visto em 2026-10-26:** a lista continua na tela depois do logout, até recarregar (observação 1).
- [ ] 2.2 Recarregue. Esperado: "Entre com o seu e-mail para ver os seus acessos." e o modal de login "Diga quem é você, antes de continuar...".
- [ ] 2.3 **Fechar o modal sem entrar** (desde 2026-11-09): feche o modal pelo X. Esperado: leva à tela inicial (`/`), em vez de deixar a tela de acessos vazia. Abra `/meus-dados/acessos` de novo e feche pela tecla Esc: o mesmo. O mesmo vale para a sessão inválida (apague o registro da sessão no ES, ou espere expirar, e recarregue): o 401 do backend abre o modal, e fechá-lo leva a `/`. Abra `/meus-dados/acessos` uma última vez para o A3.

## A3 — Novo login pelo modal da tela

- [ ] 3.1 No modal, e-mail → **Avançar** ("Você já esteve aqui conosco, obrigado pelo retorno!!!") → senha → **Login**.
- [ ] 3.2 Esperado: o modal fecha e a lista se recarrega sozinha com um acesso a mais: a nova sessão no topo (Logout **Sessão atual**) e a anterior com o logout do A2 (hora do clique em **Sair do Sistema**).

## A4 — Conferência no ES

- [ ] 4.1 O id do grupo é `sha1(sha1(email))`, como o back end escreve (BigInteger com sinal; ver `groupParentId` em `presentation/pages/meus-dados/acessos/accessesReconciliation.ts`). Em `jn_grouper` (e `jn_inactive_grouper`), o documento do grupo traz em `child` um texto JSON por login (ou logout), com as mesmas datas da tela.

## Observações da execução (2026-10-26)

| # | O que se viu | Situação |
|---|---|---|
| 1 | Depois de **Sair do Sistema**, os acessos continuam na tela até recarregar (a tela não ouve o logout). Já anotado no roteiro 03. | **a avaliar** |
| 2 | O login pelo modal da própria tela repete a busca: 10 → 11 acessos, e o logout (20:11:00) casou com o login das 19:59:53. | ok |
| 3 | Na primeira tentativa, o clique no campo de e-mail caiu no ícone de ajuda ao lado dele, que abre a explicação do campo; nada de errado na tela. | ok |
