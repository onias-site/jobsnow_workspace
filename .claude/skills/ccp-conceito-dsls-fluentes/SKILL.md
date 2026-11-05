---
name: ccp-conceito-dsls-fluentes
description: Conceito "DSLs fluentes" da taxonomia de tipos de classes Java do JobsNow. Classes das interfaces fluentes do JobsNow - consultas (CcpQuery*, CcpQueryOptions), FSED (CcpGetEntityId, CcpSelect*), fluxo (CcpTreeFlow) e configuração do bot (JnCreateStep, JnAndWithThe*). Use ao criar ou classificar um passo de DSL fluente.
---

# DSLs fluentes

## Definição

Classes que formam uma interface fluente, cada uma é um degrau da frase encadeada: consultas complexas (regra CQD), presença de registros em entidades (regra FSED), fluxo de execução e montagem da configuração do bot. Cadeias fluentes não são quebradas em variáveis (exceção da regra EE).

## Exemplos

`CcpQueryOptions`, `CcpQueryBool`, `BucketAggregation`, `CcpGetEntityId`, `CcpSelectFoundInEntity`, `CcpTreeFlow`, `CcpIfThisExecutionReturns`, `JnCreateStep`, `JnAndWithTheTemplateEntity`, o `Builder` do login

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 4 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **39** tipos (3,3% dos 1.167).

## Observações

- Reconhecida pela lista nominal `DSL` do script: degrau novo deve entrar nela.
- `CcpQueryExecutor` não é DSL (é especificação). `CcpQueryConditionType` atende também Fields e fica aqui.
