# Roteiro 02 — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

Conta: `roteiro01b.20261103@teste.com` (senha de teste `Roteiro@2026x`). Operador pelo `automacao/SupportBotCommand.java`. Antes de cada envio, `automacao/libera-cota.ps1`.

Os dados da tabela do roteiro conferiram: ORMJAVA (2), SQLDATABASE (10), NOSQLDATABASE (2), JAVA SERVER (13). A lista do ⊕ traz 108 opções (110 habilidades do currículo menos as 2 de ORMJAVA).

| Cenário | Resultado | Observação |
|---|---|---|
| H1 item a item | ok | JDBC aprovado (pai ORMJAVA no `vis_skill`), SPRING reprovado; status "Avaliado"; reprocessando com uma palavra nova no fim, ORMJAVA (2) → (3) |
| H2 item já decidido | ok | "Já reprovados anteriormente (não serão perguntados): SPRING"; e-mail com "item já reprovado em revisão anterior" |
| H3 já atendido | ok | 208 e "Solicitação já atendida" |
| H4 desassociar e aprovar | ok | BIGQUERY sem SQLDATABASE e ainda com GCP |
| H5 rejeitar tudo | ok | JPA e HIBERNATE continuam com SQLDATABASE |
| H6 validações e desistência | ok | 6.1 a 6.12 (6.13 não repetido) |
| H7 ignorar pelo ajuste | ok | 403 no ajuste **e** na sugestão de habilidade; a ignorada apagou também as pendências de habilidade da conta (SIGOM e NPORTALBRA do roteiro 01) |
| H8 `/pendingTickets` | ok | "2" volta ao primeiro depois do último, "3" → "Não entendi", resolver avulso dá baixa, e no fim "Você não tem tickets para resolver." (8.7 feito pela primeira vez) |
| H9 dois candidatos | não repetido | lógica igual à de 2026-10-26 |
| H10 comandos malformados | ok | |
| H11 termo com espaço | ok | `parent: JAVA SERVER` no avaliado |
| H12 um pedido por dia | coberto | pelo S10 do roteiro 01 e pelos 429 da cota dividida; vale o defeito D2 (48 h) |

**Base alterada (só local):** BIGQUERY saiu de SQLDATABASE; JDBC entrou em ORMJAVA (já estava pela execução de 26/10); MEMCACHE entrou em NOSQLDATABASE. **Na versão de produção deste roteiro, o operador deve rejeitar tudo:** uma aprovação muda a taxonomia real.
