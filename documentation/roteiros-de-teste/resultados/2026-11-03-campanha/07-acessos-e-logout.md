# Roteiro 07 — execução de 2026-11-03 (local, Chrome com automação)

Conta `roteiro01b.20261103@teste.com` (senha de teste `Roteiro@2026x`).

| Cenário | Resultado | Observação |
|---|---|---|
| A1 lista | ok | "1 acesso" (login das 22:01:07, logout "—") |
| A2 logout | ok | **Sair do Sistema** apagou `sessionStorage.login`; a lista ficou na tela até recarregar (observação 1 de 26/10, ainda a avaliar); ao recarregar, "Entre com o seu e-mail para ver os seus acessos." e o modal |
| A3 novo login pelo modal | ok | o modal foi direto à senha (sem a etapa "Você já esteve aqui..."); a lista se recarregou com "2 acessos": 22:42:32 no topo com "—" e 22:01:07 com logout 22:42:06 |
| A4 ES | ok | grupo `sha1(sha1(email))` com sinal: `loginDate` em `jn_grouper` e `logoutDate` em `jn_inactive_grouper`, com as datas da tela |

Nenhum defeito novo.
