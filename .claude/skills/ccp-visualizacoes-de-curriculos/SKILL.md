---
name: ccp-visualizacoes-de-curriculos
description: Mostra, só com dados de produção, o total de visualizações de currículos por dia (o de hoje desde a meia-noite de São Paulo) e as consultorias que visualizaram em cada dia. Uso - /ccp-visualizacoes-de-curriculos [dias], padrão 7.
disable-model-invocation: true
---

# Visualizações de currículos por dia

Argumento opcional: quantos dias mostrar (padrão 7). Só leitura de produção, pelo túnel: nada é gravado nem lido do Elasticsearch local.

## Passo

No PowerShell (timeout de 400000 ms; o túnel leva até 90 s):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\deploy\com-tunel-de-producao.ps1 -Script C:\eclipse-workspaces\ccp\.claude\skills\ccp-visualizacoes-de-curriculos\scripts\visualizacoes-por-dia.py -Argumentos <dias>
```

O script lê:
- o contador diário do `jn_grouper` (parent `vis_virtual_insertion_day_counter`, child `vis_viewed_resume`, chave `yyyyMMdd`), que é um histórico e não desconta exclusões;
- as visualizações de `vis_viewed_resume` e `vis_inactive_viewed_resume` pelo `insertionDate` (hora de São Paulo);
- o `vis_recruiter`, para achar o domínio de cada visualização. O e-mail da visualização é o SHA-1 no formato do Java, e domínio não profissional (`professional = false`) conta como `freelancer`.

A saída é um TSV por dia com estas colunas: contador, registros, recrutadores distintos, consultorias com a quantidade de cada uma, freelancer, onias.site e visualizações cujo recrutador não foi achado.

## Resposta

Em uma grade (skill `ccp-exibir-em-tabela`), uma linha por dia do mais antigo ao mais recente, com estas colunas: `#`, Dia, Visualizações (o contador), Recrutadores e Consultorias. Consultorias lista cada domínio com a quantidade, por exemplo `digisystem.com.br (2)`. Freelancer e onias.site ficam fora dessa coluna. Feche com a linha de total. Depois da grade, em poucas linhas:
- as faixas de horário de hoje (as visualizações logo após 00:10 vêm do e-mail diário);
- quantas visualizações de freelancer e de onias.site houve;
- quando o contador e os registros divergem, por quê: visualização excluída ou recrutador não achado.

Nunca imprima e-mails de recrutadores.

## Limites

- O contador só existe desde 2026-11-11. Antes disso, só há os registros que ainda existem.
- A coluna Consultorias vem dos registros atuais: a visualização excluída de todo lugar sai dela, mas continua no contador.
