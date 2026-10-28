# Roteiro 07 — Acessos (histórico de login) e logout

**Pré-requisito:** [00-preparacao-do-ambiente.md](00-preparacao-do-ambiente.md) até o item 4 (ambiente no ar, API js na 8082) e uma conta com senha (por exemplo, a criada no roteiro 03).

> **Criado e executado em 2026-10-26**, no Chrome, com `roteiro03.20261026@teste.com`. Tudo conferiu; notas em [Observações da execução (2026-10-26)](#observações-da-execução-2026-10-26).

## Como a tela funciona (resumo)

1. **Meus dados → Acessos** (`/meus-dados/acessos`; também no menu do usuário) lista os logins do usuário logado, do mais recente ao mais antigo: IP, navegador (User-Agent), data do login e data do logout.
2. Uma requisição só: `GET localhost:8082/grouper/{email}/jn_login_email/js_login_session_validation/<parentId>/bothSides`. Cada login grava `{userAgent, ip, loginDate}` no grupo do e-mail em `jn_grouper`; cada logout grava `{userAgent, ip, logoutDate}` no mesmo grupo em `jn_inactive_grouper`. A tela casa cada logout com o login mais recente do mesmo cliente (IP e navegador) ainda sem logout. O grupo guarda os 100 últimos de cada lado.
3. Login sem logout mostra "—" (dica: "Sem logout: a sessão expirou ou ainda está aberta"). A sessão atual é sempre a primeira linha, sem logout.
4. Sem login, a tela mostra "Entre com o seu e-mail para ver os seus acessos." e abre o modal de login; ao entrar, a busca se repete.
5. **Sair do Sistema** (menu do usuário) faz `DELETE localhost:8082/login/{email}/{sessionToken}` e apaga `sessionStorage.login`.

---

## A1 — Lista

- [ ] 1.1 Logado, abra **Acessos**. Esperado: "N acessos", colunas IP, Navegador, Login e Logout; a primeira linha é a sessão atual (Logout "—").
- [ ] 1.2 Confira os pares login/logout de sessões anteriores: cada logout fica na linha do login de onde saiu; sessões que expiraram ou foram derrubadas por outro login ficam com "—".

## A2 — Logout

- [ ] 2.1 Menu do usuário → **Sair do Sistema**. Esperado: `sessionStorage.login` apagado; o menu passa a mostrar **Entrar no sistema**.
  > **Visto em 2026-10-26:** a lista continua na tela depois do logout, até recarregar (observação 1).
- [ ] 2.2 Recarregue. Esperado: "Entre com o seu e-mail para ver os seus acessos." e o modal de login "Diga quem é você, antes de continuar...".

## A3 — Novo login pelo modal da tela

- [ ] 3.1 No modal, e-mail → **Avançar** ("Você já esteve aqui conosco, obrigado pelo retorno!!!") → senha → **Login**.
- [ ] 3.2 Esperado: o modal fecha e a lista se recarrega sozinha com um acesso a mais: a nova sessão no topo (Logout "—") e a anterior com o logout do A2 (hora do clique em **Sair do Sistema**).

## A4 — Conferência no ES

- [ ] 4.1 O id do grupo é `sha1(sha1(email))`, como o back end escreve (BigInteger com sinal; ver `groupParentId` em `presentation/pages/meus-dados/acessos/accessesReconciliation.ts`). Em `jn_grouper` (e `jn_inactive_grouper`), o documento do grupo traz em `child` um texto JSON por login (ou logout), com as mesmas datas da tela.

## Observações da execução (2026-10-26)

| # | O que se viu | Situação |
|---|---|---|
| 1 | Depois de **Sair do Sistema**, os acessos continuam na tela até recarregar (a tela não ouve o logout). Já anotado no roteiro 03. | **a avaliar** |
| 2 | O login pelo modal da própria tela repete a busca: 10 → 11 acessos, e o logout (20:11:00) casou com o login das 19:59:53. | ok |
| 3 | Na primeira tentativa, o clique no campo de e-mail caiu no ícone de ajuda ao lado dele, que abre a explicação do campo; nada de errado na tela. | ok |
