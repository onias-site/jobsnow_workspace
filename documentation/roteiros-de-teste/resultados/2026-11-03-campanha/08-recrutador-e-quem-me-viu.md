# Roteiro 08 e dinâmica candidato/recrutador — execução de 2026-11-03 (local, Chrome com automação, e-mail mock)

## Massa

| Papel | Contas |
|---|---|
| Candidatos (currículo ativo) | `roteiro01b` (TI, CLT 9.500, LinkedIn próprio), `roteiro04a`, `04b`, `04c`, `04f`, `04g` (tipo 4, CLT 2.500). `04c` usa o LinkedIn de `04a`, que sobrou do C6 do roteiro 04 |
| Recrutadores fictícios | 2 freelancers: `recrutadora.20261103@gmail.com`, `recrutadorb.20261103@gmail.com`; 2 do mesmo domínio: `recrutador1` e `recrutador2.20261103@empresa09.com.br`; 1 de outro domínio: `recrutador.20261103@consultoria09.com.br` |
| Recrutador logado na tela | `roteiro01b.20261103@teste.com` |

Todas as contas têm a senha de teste `Roteiro@2026x`. Os sufixos `.20261103@teste.com` foram omitidos acima.

Envio: `automacao/SendResumesToRecruiters.java` com os 6 recrutadores → 6 e-mails, `resumesFound: 1013`. O reset de hoje fez todos os currículos contarem como alterados nos últimos 7 dias, e os candidatos de teste ficaram fora dos 40 primeiros do e-mail. Os links assinados deles saíram do `GET /recruiter/{email}/resumes-of-the-week` de cada recrutador, o mesmo que a tela **Currículos da semana** usa. O `resumeId` é `sha1(sha1(email))` com sinal. Script temporário: `C:\Users\Hp Elitebook\.claude\jobs\271268fc\tmp\dyn.mjs`.

## Visualizações feitas

| Recrutador | 01b | 04a | 04b | 04c | 04f | 04g |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| recrutadora (gmail) | ✔ tela + 2ª vez | ✔ | | | ✔ | |
| recrutadorb (gmail) | ✔ | | ✔ | | | |
| recrutador1 (empresa09) | ✔ | ✔ | | ✔ | | |
| recrutador2 (empresa09) | ✔ | | | | | ✔ |
| consultoria09 | ✔ | ✔ | ✔ | ✔ | | |
| roteiro01b (tela) | | ✔ | | | | |

## Quem me viu (novembro), logado com cada candidato

| Candidato | Tela | Esperado | Situação |
|---|---|---|---|
| 01b | 5: empresa09.com.br 2, freelancer 2, consultoria09.com.br 1 | igual | ok; a 2ª visualização da recrutadora não contou |
| 04a | 4: consultoria09 1, empresa09 1, freelancer 1, teste.com 1 | igual | ok |
| 04b | 2: consultoria09 1, freelancer 1 | igual | ok |
| 04c | 4: os mesmos números de 04a | 2 se fosse por e-mail | **por projeto**: `VisResumeViewsOfTheMonthCombinations` conta a visualização para cada e-mail que usa o LinkedIn visto, e 04a e 04c usam o mesmo |
| 04f | 1: freelancer 1 | igual | ok |
| 04g | 1: empresa09 1 | igual | ok |

## Roteiro 08

| Cenário | Resultado | Observação |
|---|---|---|
| R1 e-mail | ok | 6 e-mails, 40 linhas com **Ver currículo** e o link de descadastro |
| R2 ver currículo | ok | 2.1 token alterado → "Este link não é válido..."; 2.2 "Não" → "O currículo não foi aberto..."; 2.3 LinkedIn aberto e apelido sugerido "JAVA_JAVASCRIPT_SQL_DATABASE_CLOUD_R$ 9.500,00_São Paulo – SP_12 Anos" (69 caracteres); 2.4 `Dev` desabilita, "Dev Java do roteiro 08" salva |
| R3 Quem me viu | ok | ver a tabela acima; 3.3 em outubro, "Nenhum recrutador viu o seu currículo neste mês." |
| R4 telas do recrutador | ok | **Currículos da semana**: "1013 currículos...", 5 colunas, um link por linha, e **Ver currículo** de 04a pela própria tela; **Currículos visualizados**: "1 currículo visualizado no mês" e **ver detalhes** expande. Pela API, a recrutadora tem 3 itens, a recrutadorb 2, a recrutador1 2 (04a e 04c viram 1, pelo LinkedIn), a recrutador2 2 e a consultoria09 3 |
| R5 descadastrar | ok | 5.1 a 5.4; `recrutadorb` foi para `vis_inactive_recruiter` |

## Notas para atualizar o roteiro

1. Desde 2026-11-01, o campo Mês/ano das telas **Quem me viu** e **Currículos visualizados** abre no mês anterior (decisão do usuário, `MonthPicker`). Para ver o mês corrente, é preciso escolhê-lo. O 3.1 e o 4.1 do roteiro ainda dizem "no mês corrente".
2. O caminho das APIs leva o e-mail cru: com `%40`, o vis responde 422.
3. A sessão vale para o IP e o User-Agent de quem a abriu. Uma sessão aberta pelo Node em `127.0.0.1` dá 401 no Chrome, que chega por `::1`; abra-a em `localhost`.
4. As contas criadas pelos meus scripts com `goal: recruiting` entraram em `vis_recruiter` (fonte `login`). Na versão de produção, os candidatos fictícios devem usar o objetivo de candidato.
