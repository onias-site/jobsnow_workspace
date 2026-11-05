---
name: ccp-conceito-business
description: Conceito "Business" da taxonomia de tipos de classes Java do JobsNow. Classe ou enum que implementa CcpBusiness, direta ou indiretamente (regra SBT). Use ao criar, classificar ou revisar uma ação do JobsNow.
---

# Business

## Definição

Classe ou item de enum que implementa `CcpBusiness` (`Function<CcpJsonRepresentation, CcpJsonRepresentation>`), direta ou indiretamente: toda ação do sistema (regra SBT). Valida a entrada em `execute` com `CcpJsonValidatorEngine.validateJson` (regra DLV) e é chamada por `execute`, nunca por `apply`.

## Exemplos

`CcpBusinessDeleteRecordFromEntity`, `JnBusinessDailyDatabaseMaintenance`, `JnMessageTemplate`, os serviços `JnService` (ex.: `VisServiceSkills`), os passos de bot executados pelo nome da classe

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 2 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **181** tipos (15,5% dos 1.167).

## Observações

- Vence Fields: `CcpBusiness` estende `CcpJsonFieldName`, então os 165 business também atendem Fields; o usuário decidiu em 2026-11-04 que contam como Business.
- Vence Especificação / implementação (16 casos, ex.: `CcpHttpApiExecutor`, transformadores de campo).
