---
name: ccp-conceito-entidades-de-dados
description: Conceito "Entidades de dados" da taxonomia de tipos de classes Java do JobsNow. Classe que declara `public static final CcpEntity ENTITY` (tabela do Elasticsearch). Use ao criar, renomear, classificar ou revisar uma entidade de dados do JobsNow.
---

# Entidades de dados

## Definição

Classe que declara `public static final CcpEntity ENTITY`: a definição de uma tabela (índice do Elasticsearch). Os campos ficam num enum `Fields` aninhado, com as anotações de validação e de chave primária. O comportamento vem das anotações de decorator na classe (AEI, ED, SEA, DSE, VE, TWE, ROE, CE, AE, GE, LFE do CLAUDE.md).

## Exemplos

`JbEntityBot`, `JnEntityGrouper`, `VisEntityResume`, `JsEntityLoginPassword`, entidades virtuais como `VisEntityStatisSkill`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 1 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **83** tipos (7,1% dos 1.167).

## Observações

- Vence Especificação / implementação (76 entidades implementam interfaces dela) e Esquemas de validação de entrada (4 entidades virtuais só com campos validados).
- Entidade nova é cacheável de hora em hora (`@CcpEntityCache(3600)`), e criar uma entidade exige script de transporte para produção (skill `ccp-transporte-para-producao`).
