---
name: ccp-curriculos-de-producao-a-um-recrutador
description: Envia a um único recrutador o e-mail de currículos (VisNotifyRecruiterAboutResumes) com TODOS os vis_resume de produção, só com dados de produção (sem ES local e sem simulação). Uso - /ccp-curriculos-de-producao-a-um-recrutador <e-mail> [<e-mail> ...].
disable-model-invocation: true
---

# Todos os currículos de produção a um recrutador

Argumentos: um ou mais e-mails de recrutador. Sem e-mail válido, mostre o uso em uma linha e não rode nada.

**Só produção (desde 2026-11-15):** a skill não olha o Elasticsearch local nem simula. Tudo vem de produção e vai para produção.

## O que faz

`documentation/roteiros-de-teste/automacao/enviar-curriculos-de-producao-a-um-recrutador.ps1`, com um único túnel de produção aberto:
1. lê produção, só leitura (`ler-curriculos-de-producao.py`): todos os `vis_resume`, os rankings de `vis_skill`, as datas e as visualizações do histórico (grupos `jn_virtual_versionable_history` do `jn_grouper`, desde 2026-11-20), os apelidos de `vis_viewed_resume` e os pares de `vis_inactive_viewed_resume`, para um arquivo temporário (apagado no fim);
2. roda `SendProductionResumesToRecruiter.java` com o Elasticsearch de produção (`elasticsearch.address`/`secret` do túnel) e as chaves de produção (`tokenEmailKey`, `urlEmailKey`, `recruiterLinksSecret`), trocadas só no processo do java, com as regras do processo diário (`VisBusinessSendResumesToRecruiters`, por reflexão): ordem, `notAllowedCompany` do domínio, última visualização, apelido, links assinados e descadastro. Sem janela de 7 dias, fim de semana, fila ou limite diário; o recrutador não precisa estar em `vis_recruiter`;
3. template e parâmetros de envio são os de produção; a marca de "já enviado hoje" desse destinatário em produção é apagada antes do envio (para reenviar no mesmo dia);
4. o próprio envio grava em produção a lista inteira da tela "Ver todos" (`vis_recruiter_resumes`, descartável diário do recrutador), conferida relendo (`OK lista da tela Ver todos em producao linhas=N relidas=N`).

## Passos

No PowerShell, com caminho absoluto, um e-mail por vez. Timeout de 420000 ms (o túnel leva até 90 s e o Maven compila):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\roteiros-de-teste\automacao\enviar-curriculos-de-producao-a-um-recrutador.ps1 -Email <e-mail>
```

Front e API têm padrão `https://onias.site` e `https://api.onias.site` (`-Front`, `-ApiVis` para trocar).

## Resposta

Em uma grade (skill `ccp-exibir-em-tabela`), uma linha por e-mail: currículos em produção, linhas do recrutador, quantos no e-mail (máximo 30), se o SendGrid aceitou (`OK` / `FALHOU`; saída 3 = aviso em `jn_jobsnow_warning` de produção) e se a lista "Ver todos" conferiu em produção (saída 5 = não conferiu). Nunca imprima e-mails de candidatos nem valores de `producao.json`.

## Limites

- A lista "Ver todos" vale no dia do envio (descartável diário). Se o recrutador abriu a tela na última hora com outra lista gravada, o cache de produção (1 h, Valkey) pode mostrar a anterior até vencer.
- Endereço de destino real: confirme com o usuário antes de enviar a alguém que não seja ele mesmo.
