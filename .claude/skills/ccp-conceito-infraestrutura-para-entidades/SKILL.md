---
name: ccp-conceito-infraestrutura-para-entidades
description: Conceito "Infraestrutura para entidades de dados" da taxonomia de tipos de classes Java do JobsNow. CcpEntity e todos os seus descendentes (decorators de entidade, delegators, JnDisposableEntity, JnGrouperChild*) mais CcpBulkItem. Use ao criar ou classificar um decorator de entidade ou peça do motor de entidades.
---

# Infraestrutura para entidades de dados

## Definição

A interface `CcpEntity` e todos os seus descendentes, em qualquer profundidade (filhas, netas, bisnetas...): os decorators de entidade catalogados em `CcpEntityDecoratorTypes` (regra ED) e as classes de comportamento passadas nas anotações. Inclui também `CcpBulkItem`, o item de uma operação em lote sobre uma entidade (decisão de 2026-11-04).

## Exemplos

`CcpEntityDelegator`, `CcpDefaultEntityDelegator`, `DecoratorTwinEntity`, `DecoratorCacheEntity`, `JnDisposableEntity`, `JnVersionableEntity`, `JnGrouperChildEntityBeforeWrite`, `CcpBulkItem`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 3 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **26** tipos (2,2% dos 1.167).

## Observações

- Vence Especificação / implementação (`CcpEntity` fica em `com.ccp.especifications`) e Fields (`CcpEntity` estende `CcpJsonFieldName`).
- Todo decorator de entidade vive no centro de custo ccp; o que ele precisa de outro centro de custo entra como parâmetro da anotação.
