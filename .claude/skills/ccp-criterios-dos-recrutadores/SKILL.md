---
name: ccp-criterios-dos-recrutadores
description: Mostra, só com dados de produção, os critérios que escolhem os recrutadores do próximo envio diário do e-mail de currículos (VisBusinessSendResumesToRecruiters) e quantos serão escolhidos em cada critério; grava a lista dos escolhidos num TSV. Uso - /ccp-criterios-dos-recrutadores
disable-model-invocation: true
---

# Critérios dos recrutadores do próximo envio

Sem argumentos. Só leitura de produção, pelo túnel: nada é gravado em produção nem lido do Elasticsearch local.

## Passo

No PowerShell (timeout de 400000 ms; o túnel leva até 90 s), com a data do dia no nome do arquivo:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\deploy\com-tunel-de-producao.ps1 -Script C:\eclipse-workspaces\ccp\.claude\skills\ccp-criterios-dos-recrutadores\scripts\criterios-dos-recrutadores.py -Argumentos C:\logs\curriculos-aos-recrutadores\proximos-recrutadores-<aaaa-mm-dd>.tsv
```

O script simula `getRecruitersInOrder` (ordem de 2026-11-15) com os dados de produção: recrutadores ativos de `vis_recruiter` (campos `legacyActive`, `lastLegacyView`, `lastTelegramAppearance`, `source`, `professional`), última visualização do `jn_versionable` e de `vis_recruiter_sign_up_return`, `vis_recruiter_first_email` e os cursores do rodízio em `vis_recruiter_queue_cursor`. Depois aplica o filtro de endereço inválido e corta em 2.000 (`RECRUITERS_PER_DAY`).

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

- É uma simulação: o envio de verdade roda às 00:10 (America/Sao_Paulo) no Cloud Run Job `jobsnow-processo-diario`; quem visualizar ou se cadastrar até lá muda a lista. Recrutador cuja lista de currículos sai vazia (todos proíbem a empresa do domínio) não recebe, e o simulador não desconta isso.
- Se a ordem de `VisBusinessSendResumesToRecruiters.getRecruitersInOrder` mudar, atualize o script junto.
