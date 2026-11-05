---
name: ccp-conceito-anotacoes
description: Conceito "Anotações" da taxonomia de tipos de classes Java do JobsNow. Tipos @interface do JobsNow - as anotações de side effect (Before/After), de decorator de entidade e de validação de campo, todas no ccp. Use ao criar, classificar ou revisar uma anotação.
---

# Anotações

## Definição

Tipos `@interface`, todos em `ccp_commons_jobsnow`. É a maior categoria. Subgrupos: side effect de escrita e de transferência (`@CcpBefore*`/`@CcpAfter*`, cerca de 320, regra SEA), decorators de entidade (`@CcpEntity*`), validação e valor padrão de campo (`@CcpJsonField*`), validações globais, `@CcpAllowNullParameter`/`@CcpAllowNullReturn` (regra NL).

## Exemplos

`@CcpAfterSaveFromMainEntity`, `@CcpBeforeTransferDataFromMainEntity`, `@CcpEntityTwin`, `@CcpEntityCache`, `@CcpEntityDisposable`, `@CcpJsonFieldValidatorRequired`, `@CcpAllowNullParameter`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 10 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **357** tipos (30,6% dos 1.167).

## Observações

- Nenhuma anotação é aninhada em outra, e anotação de parâmetro único o chama de `value` (regra ED).
- Atributos de anotação mantêm literais (exceção da regra LL).
