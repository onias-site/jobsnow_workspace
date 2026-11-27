---
name: ccp-criterios-dos-recrutadores
description: Mostra, só com dados de produção, os critérios que escolhem os recrutadores do dia do e-mail de currículos (enviado de hora em hora, 04:00 a 23:00, segunda a sexta) (VisBusinessSendResumesToRecruiters) e quantos serão escolhidos em cada critério; grava a lista dos escolhidos num TSV. Uso - /ccp-criterios-dos-recrutadores
disable-model-invocation: true
---

# Critérios dos recrutadores do próximo envio

Sem argumentos. Só leitura de produção, pelo túnel: nada é gravado em produção nem lido do Elasticsearch local.

## Passo

No PowerShell (timeout de 400000 ms; o túnel leva até 90 s), com a data do dia no nome do arquivo:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\deploy\com-tunel-de-producao.ps1 -Script C:\eclipse-workspaces\ccp\.claude\skills\ccp-criterios-dos-recrutadores\scripts\criterios-dos-recrutadores.py -Argumentos C:\logs\curriculos-aos-recrutadores\proximos-recrutadores-<aaaa-mm-dd>.tsv
```

O script simula `getRecruitersInOrder` (ordem de 2026-11-15) com os dados de produção: recrutadores ativos de `vis_recruiter` (campos `legacyActive`, `lastLegacyView`, `lastTelegramAppearance`, `source`, `professional`), última visualização do histórico de `vis_viewed_resume` (grupos `jn_virtual_versionable_history` do `jn_grouper`, desde 2026-11-20) e de `vis_recruiter_sign_up_return`, `vis_recruiter_first_email` e os cursores do rodízio em `vis_recruiter_queue_cursor`. Depois aplica o filtro de endereço inválido e corta em 2.000 (`RECRUITERS_PER_DAY`), o total do dia que as 20 execuções horárias repartem.

## Resposta

Em uma grade (skill `ccp-exibir-em-tabela`), uma linha por critério, na ordem de prioridade, com: o critério, quantos recrutadores há no grupo (linha "tamanho de cada grupo na ordem completa"), quantos serão escolhidos no próximo envio (os que faltam na saída = 0) e a ordem dentro do grupo. Linha de total: recrutadores ativos e 2.000.

| # | Critério | Ordem dentro do grupo |
|---|---|---|
| 1 | Visualizou currículo nos últimos 35 dias | visualização mais recente primeiro |
| 2 | Cadastrou-se e aguarda o 1º e-mail | hash do e-mail |
| 3 | Apareceu no Telegram nos últimos 183 dias | aparição mais recente (sem rodízio) |
| 4 | Visualizou currículo no legado | visualização mais recente, em rodízio |
| 5 | Ativo no legado (`legacyActive`) | hash do e-mail, em rodízio |
| 6 | Domínio não profissional | hash do e-mail, em rodízio |
| 7 | Fila de quem nunca visualizou | cadastro primeiro, depois hash, em rodízio |

Cada recrutador entra só no primeiro critério que atende; quem visualizou há mais de 35 dias e parou fica de fora. Depois da grade, em poucas linhas: inválidos pulados, ativos no legado na lista, se os cursores do rodízio já existem (vazios = o rodízio começa do início) e o caminho do TSV. Nunca imprima e-mails de recrutadores na resposta, salvo se o usuário perguntar por um específico.

## Limites

- É uma simulação da lista do dia. O envio de verdade roda no Cloud Run Job `jobsnow-curriculos-aos-recrutadores` (America/Sao_Paulo), em execuções de hora em hora.
  - Horário: desde 2026-11-27, `0 4-23 * * 1-5`, de 04:00 a 23:00, de segunda a sexta. Até 2026-11-26 era uma execução às 10:00, e antes de 2026-11-18, às 00:10.
  - Cada execução recalcula a ordem, manda para a 20ª parte de `recruitersPerDay` (cerca de 100) e pula quem já recebeu no dia (`vis_recruiter_resumes`), os recrutadores com vaga ativa que recebe e-mail próprio, e o fim de semana. O simulador não desconta esses casos.
  - Quem recebeu a lista de currículos de uma vaga do `/salvarVaga` já tem o e-mail do dia e também é pulado.
  - Quem visualizar ou se cadastrar ao longo do dia muda a ordem das execuções seguintes. No fim de semana nada sai, e a lista vale para a segunda. Recrutador cuja lista de currículos sai vazia (todos proíbem a empresa do domínio) não recebe, e o simulador não desconta isso.
- Se a ordem de `VisBusinessSendResumesToRecruiters.getRecruitersInOrder` mudar, atualize o script junto.
