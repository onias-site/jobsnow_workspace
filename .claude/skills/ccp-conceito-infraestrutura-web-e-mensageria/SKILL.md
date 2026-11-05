---
name: ccp-conceito-infraestrutura-web-e-mensageria
description: Conceito "Infraestrutura web e de mensageria" da taxonomia de tipos de classes Java do JobsNow. Filtros e wrappers de servlet, ControllerAdvice, tratador de exceções Spring e peças dos consumidores e publicadores do Pub/Sub e do leitor do bot. Use ao criar ou classificar infraestrutura de API REST ou de mensageria.
---

# Infraestrutura web e de mensageria

## Definição

Peças técnicas das APIs REST e da mensageria que não são ponto de entrada: filtros e wrappers de servlet, `ControllerAdvice` (tratador de exceções, removedor de valores da sessão, cabeçalhos de cache), receptores e consumidores do Pub/Sub, publicação no Pub/Sub, mensageria assíncrona local, leitor do bot.

## Exemplos

`CcpValidEmailFilter`, `CcpPutSessionValuesRequestWrapper`, `CcpRestApiExceptionHandlerSpring`, `VisRestApiSkillStatisticsCacheHeader`, `CcpMessageReceiver`, `CcpPubSubTopicConsumer`, `GcpPubSubSdkPublishing`, `AsyncMensageriaProcessRun`, `JbInstantMessengerMessageReader`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 6 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **22** tipos (1,9% dos 1.167).

## Observações

- Reconhecida pela lista nominal `WEB` do script.
- Controllers, interfaces OpenAPI, starters e classes com `main` não entram aqui: são Ignorados (pontos de entrada).
