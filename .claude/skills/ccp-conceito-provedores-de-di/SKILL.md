---
name: ccp-conceito-provedores-de-di
description: Conceito "Provedores de DI" da taxonomia de tipos de classes Java do JobsNow. Implementações de CcpInstanceProvider, uma por módulo de tecnologia (CcpGsonJsonHandler, CcpElasticSearchCrud, CcpSendGridEmailProvider) e as locais do ccp_mocking. Use ao criar ou classificar a ligação de uma especificação à sua implementação.
---

# Provedores de DI

## Definição

Classes e enums que implementam `CcpInstanceProvider`: entregam ao `CcpDependencyInjection` a implementação de uma especificação. Há um por módulo de tecnologia, mais os enums locais do `ccp_mocking_jobsnow`. Conceitualmente completam a categoria Especificação / implementação.

## Exemplos

`CcpGsonJsonHandler`, `CcpElasticSearchCrud`, `CcpElasticSerchDbBulk`, `CcpSendGridEmailProvider`, `CcpGcpMemoryStore`, `CcpTelegramInstantMessenger`, `CcpLocalInstances`, `CcpLocalCacheInstances`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 12 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **16** tipos (1,4% dos 1.167).

## Observações

- Vence Enum complexo (`CcpLocalInstances`, `CcpLocalCacheInstances`).
