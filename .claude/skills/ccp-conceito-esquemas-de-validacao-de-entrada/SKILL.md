---
name: ccp-conceito-esquemas-de-validacao-de-entrada
description: Conceito "Esquemas de validação de entrada" da taxonomia de tipos de classes Java do JobsNow. Classes sem supertipo e sem métodos, só com campos anotados por @CcpJsonFieldValidator* / @CcpJsonCopyFieldValidationsFrom, que descrevem a entrada de um serviço (CreateLoginEmail, ExecuteLogin). Use ao criar ou classificar as regras de entrada de um serviço (regra DLV).
---

# Esquemas de validação de entrada

## Definição

Classes sem supertipo e sem métodos, cujos campos (`Object`) só carregam anotações de validação. Descrevem as regras de entrada de um serviço, lidas pelo `CcpJsonValidatorEngine` (regra DLV). Não são DTO: nada é instanciado com elas.

## Exemplos

`CreateLoginEmail`, `CreateLoginToken`, `ExecuteLogin`, `ExecuteLogout`, `ExistsLoginEmail`, `ResendLoginToken`, `SaveAnswers`, `SavePassword`, `UnlockLoginToken` (todas em `com.js.services`)

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 18 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **9** tipos (0,8% dos 1.167).

## Observações

- Perde para Entidades de dados: entidades virtuais com campos validados contam como entidade.
