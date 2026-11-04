# Roteiro 01 — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

Contas: `roteiro01.20261103@teste.com` (S1–S7, S9 parcial) e `roteiro01b.20261103@teste.com` (S8–S10). Senha de teste das duas: `Roteiro@2026x`. Operador pelo `automacao/SupportBotCommand.java`.

Base: depois do reset de 2026-11-03 com os dados preservados (`automacao/preservar-dados-no-reset.ps1`). Como o `vis_skill` foi preservado, `PICK BY LIGHT` e `LINUX EMBARCADO` (aprovadas em execuções antigas) já eram habilidades conhecidas.

| Cenário | Resultado | Observação |
|---|---|---|
| S1 aprovada | ok | `STATE MACHINE` no lugar de `PICK BY LIGHT` (sinônimos `MAQUINA DE ESTADOS`, `FSM`, `FINITE STATE MACHINE`). A aba mostra **109** habilidades e **38** conhecimentos implícitos (o roteiro diz 105/36: mudou com a revisão do synonyms.json). Depois do reprocessamento, 109 → 110. Ticket com `priority` **4** (o roteiro diz 3: desde o `/solveStackTrace` a prioridade 0 é do erro não tratado e as outras subiram 1). |
| S2 rejeitada | ok | e-mail com `&lt;projeto&gt;` escapado |
| S3 validações | ok | |
| S4 desistência e variantes | ok | 4.1 a 4.10, inclusive "Sugestão não encontrada" depois da rejeição com o modal aberto |
| S5 ignorar | ok | 5.8 (ajuste de hierarquia com 403) fica para o roteiro 02 |
| S6 `/pendingTickets` | ok | também com habilidade de várias palavras (`ASSINADOR DIGITAL`, sinônimo `ASSINATURA DIGITAL`) pelo "1" |
| S7 bloqueios da tela | ok | |
| S8 outra conta | ok | 410 depois do login, "Rejeitada" com o motivo, `vis_skill_reviewed` sem e-mail |
| S9 sinônimo de sugestão pendente | ok | `SIGOM` com sinônimo `SISTEMA DE GESTAO ORCAMENTARIA` |
| S10 limite diário | ok, defeito corrigido | ver D2 |

## Defeitos achados

- **D1 — script de liberação de cota (roteiro 00, 5A) errava a marca do cache.** O Java nomeia a marca com `new BigInteger(sha1).toString(16)`, **com sinal**; o script calculava sem sinal, então metade das chaves ficava sem marca e a tela seguia dando 429 até reiniciar a API. Também faltava marcar a chave da cópia em `jn_disposable_record`. **Corrigido** no roteiro 00 e em `automacao/libera-cota.ps1`.
- **D2 — a cota diária bloqueia por 48 horas, e não por 24.** Uma única gravação de `jn_ticket_daily_limit` gera a cópia em `jn_disposable_record` com `trueTimestamp` = envio **+ 24 h** e `timestamp` (validade) = envio **+ 48 h** (medido: 24,001 h e 48,001 h). Simulando no ES local que as 24 horas passaram (só o `trueTimestamp` no passado), o envio continua recusado com 429: vale o `timestamp`. É o "A conferir" do 10.2 (visto em 2026-10-26). **Corrigido em 2026-11-03.** Causa: `CcpDefaultEntityDelegator.save` monta os itens do bulk uma vez e funde o json da cópia (já com a validade, agora + 24 h) aos parâmetros. O handler monta os itens de novo sobre esse json, e `JnDisposableEntity.populateAnExpurgableFromJson` lia esse `timestamp` como o momento da gravação. Valia para toda entidade descartável sem `timestamp` próprio. Agora `getWriteMoment` só usa o `timestamp` quando é campo da própria entidade; senão usa o agora. Conferido pela API (cópia nova com validade de 24,0 h). Regressão: `JnEntityTicketDailyLimitDecoratorsTest` falha sem a correção (+86.400.247 ms) e passa com ela; os 116 testes de decorator dos descartáveis passam. **Falta o deploy em produção.**
