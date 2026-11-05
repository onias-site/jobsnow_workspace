---
name: ccp-conceito-fields
description: Conceito "Fields" da taxonomia de tipos de classes Java do JobsNow. Tipos que implementam CcpJsonFieldName - os enums de nomes de campo (Fields, CcpJsonCommonsFields, JnJsonCommonsFields) e CcpFieldName/CcpEntityField. Use ao criar ou classificar um enum de field name (regra LL).
---

# Fields

## Definição

Tipos que implementam `CcpJsonFieldName`: os enums de nomes de campo usados nos acessores de `CcpJsonRepresentation` (regra LL), os centralizadores e as classes de nome de campo. Os enums `Fields` aninhados (cerca de 340 arquivos) não contam como tipo separado.

## Exemplos

`CcpJsonCommonsFields`, `JnJsonCommonsFields`, `JnJsonInstantMessengerFields`, `VisJsonCommonsFields`, `CcpBulkScriptedUpdateFields`, `CcpFieldName`, `CcpEntityField`, `CcpProcessStatus`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 14 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **89** tipos (7,6% dos 1.167).

## Observações

- Perde para Business (todo `CcpBusiness` estende `CcpJsonFieldName`), Infraestrutura para entidades (`CcpEntity` também), Motores e DSL.
- Vence Enum complexo: um enum de field name implementa interface, mas conta aqui.
- Antes de criar um item, procure-o nos centralizadores.
