---
name: ccp-slowlog-producao
description: Liga, desliga ou consulta o slowlog de todas as queries no Elasticsearch de produção (script 33, pelo túnel IAP na porta 9210). Uso - /ccp-slowlog-producao ligar, /ccp-slowlog-producao desligar ou /ccp-slowlog-producao situacao.
disable-model-invocation: true
---

# Slowlog de todas as queries em produção

O argumento é `ligar`, `desligar` ou `situacao`. Sem argumento, use `situacao`. Com outro valor, mostre o uso em uma linha e não rode nada.

## Passo

No PowerShell, com caminhos absolutos (o `!` do Bash apaga as barras invertidas):

```powershell
Set-Location C:\eclipse-workspaces\ccp; powershell -NoProfile -ExecutionPolicy Bypass -File documentation\deploy\com-tunel-de-producao.ps1 -Script documentation\deploy\33-slowlog-de-todas-as-queries.py -Argumentos <ligar|desligar|situacao>
```

Use um timeout de 240000 ms (o túnel leva até 90 s para abrir).

## Resposta

Responda em uma ou duas linhas: o cluster (deve ser `jobsnow-prd`) e quantos índices ficaram com e sem o slowlog de todas as queries.
- Depois de `ligar`: lembre que o slowlog grava o corpo das queries (pode ter e-mails) no disco da VM e no Cloud Logging, e que é preciso desligar depois.
- Um índice criado depois de ligar não herda o limite: para ele, basta rodar `ligar` de novo.
