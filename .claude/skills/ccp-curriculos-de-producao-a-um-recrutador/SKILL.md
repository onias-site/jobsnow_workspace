---
name: ccp-curriculos-de-producao-a-um-recrutador
description: Envia a um único recrutador o e-mail de currículos (VisNotifyRecruiterAboutResumes) com TODOS os vis_resume de produção, lidos só para leitura pelo túnel IAP. Uso - /ccp-curriculos-de-producao-a-um-recrutador <e-mail> [simular].
disable-model-invocation: true
---

# Todos os currículos de produção a um recrutador

Argumentos: o e-mail do recrutador (obrigatório) e, opcionalmente, `simular`. Sem e-mail válido, mostre o uso em uma linha e não rode nada.

## O que faz

`documentation/roteiros-de-teste/automacao/enviar-curriculos-de-producao-a-um-recrutador.ps1`:
1. lê produção, **só leitura**, pelo túnel (`ler-curriculos-de-producao.py`): todos os `vis_resume`, os rankings de `vis_skill`, as datas e as visualizações do `jn_versionable` e os apelidos de `vis_viewed_resume`, para um arquivo temporário (apagado no fim);
2. roda `SendProductionResumesToRecruiter.java` contra o ES **local**, com as regras do processo diário (`VisBusinessSendResumesToRecruiters`, por reflexão): ordem, `notAllowedCompany` do domínio, última visualização, apelido, links assinados e descadastro. Sem janela de 7 dias, fim de semana, fila ou limite diário; o recrutador não precisa estar em `vis_recruiter`;
3. troca, só no processo do java, `tokenEmailKey`, `urlEmailKey` e `recruiterLinksSecret` pelos de `C:\segredos\producao.json`, para o SendGrid aceitar e os links valerem em produção;
4. só no modo `enviar`, com o e-mail aceito: grava em produção, pelo túnel e pela própria entidade (modo `gravar-lista` do java, com `elasticsearch.address`/`secret` de produção), a lista inteira da tela "Ver todos" (`vis_recruiter_resumes`, descartável diário do recrutador) e confere relendo (`OK gravar-lista linhas=N relidas=N`). Sem isso o link "Ver todos" abria a tela vazia em produção (corrigido em 2026-11-12).

A única gravação em produção é essa lista, e só no envio. A marca local de "já enviado hoje" desse destinatário é apagada antes do envio, então dá para simular e enviar no mesmo dia.

## Passos

No PowerShell, com caminho absoluto. Timeout de 420000 ms (o túnel leva até 90 s e o Maven compila):

1. Sempre simule primeiro:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\roteiros-de-teste\automacao\enviar-curriculos-de-producao-a-um-recrutador.ps1 -Modo simular -Email <e-mail>
```
   Confira `C:\logs\email\<e-mail>\com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes.html`: no máximo 30 linhas na tabela, "(N no total)" e "30 primeiros de N" com N = linhas do recrutador, nenhum `{placeholder}` cru, links para `https://onias.site`.
2. Se o argumento não for `simular`, envie:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\eclipse-workspaces\ccp\documentation\roteiros-de-teste\automacao\enviar-curriculos-de-producao-a-um-recrutador.ps1 -Modo enviar -Email <e-mail>
```

Front e API têm padrão `https://onias.site` e `https://api.onias.site` (`-Front`, `-ApiVis` para trocar).

## Resposta

Em uma grade (skill `ccp-exibir-em-tabela`): currículos em produção, linhas do recrutador, quantos no e-mail (máximo 30), se o SendGrid aceitou (`OK` / `FALHOU`; saída 3 = aviso em `jn_jobsnow_warning` local) e se a lista "Ver todos" foi gravada em produção (saída 5 = não foi). Nunca imprima e-mails de candidatos nem valores de `producao.json`.

## Limites

- O template e os parâmetros de envio são os do ES local: se o template de produção mudou e o local não, o e-mail sai com o texto local.
- A lista "Ver todos" vale no dia do envio (descartável diário). Se o recrutador abriu a tela na última hora com outra lista gravada, o cache de produção (1 h) pode mostrar a anterior até vencer.
- Endereço de destino real: confirme com o usuário antes de enviar a alguém que não seja ele mesmo.
