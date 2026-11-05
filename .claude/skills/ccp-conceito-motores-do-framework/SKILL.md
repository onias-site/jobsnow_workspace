---
name: ccp-conceito-motores-do-framework
description: Conceito "Motores e infraestrutura do framework" da taxonomia de tipos de classes Java do JobsNow. Classes que fazem o framework funcionar - DI (CcpDependencyInjection), fábrica e metadados de entidade, motores de validação e de valor padrão, receptor de mensageria, motor do bot, HTTP. Use ao criar ou classificar uma peça interna do framework.
---

# Motores e infraestrutura do framework

## Definição

Classes que não são ação, entidade nem decorator, mas fazem o framework funcionar: injeção de dependência, fábrica e metadados das entidades, motores de validação e de valores padrão, receptor da mensageria, motor do bot, peças do cliente HTTP e resultados de bulk.

## Exemplos

`CcpDependencyInjection`, `CcpEntityFactory`, `CcpEntityMetaData`, `CcpJsonValidatorEngine`, `CcpJsonFieldDefaultValuesEngine`, `CcpMensageriaReceiver`, `JnMensageriaReceiver`, `JbBotEngine`, `CcpHttpHandler`, `CcpToStringBuilder`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 5 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **22** tipos (1,9% dos 1.167).

## Observações

- Reconhecida pela lista nominal `ENGINE` do script.
- `CcpMensageriaReceiver` e `JnMensageriaReceiver` atendem também Fields e ficam aqui.
