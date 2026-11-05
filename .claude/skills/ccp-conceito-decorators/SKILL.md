---
name: ccp-conceito-decorators
description: Conceito "Decorators" da taxonomia de tipos de classes Java do JobsNow. Decorators do pacote com.ccp.decorators (implementam CcpDecorator ou terminam em Decorator) e CcpJsonRepresentation. Use ao criar ou classificar um decorator de API (arquivo, texto, JSON, tempo, reflexão etc.), regra DEW.
---

# Decorators

## Definição

Classes que envolvem uma API de muitas operações (arquivo, pasta, stream, coleção, e-mail, hash, número, senha, propriedades, reflexão, string, texto, tempo, URL) atrás de uma interface própria do JobsNow, no pacote `com.ccp.decorators` (regra DEW). `CcpJsonRepresentation` é o decorator do JSON, embora não implemente `CcpDecorator`.

## Exemplos

`CcpFileDecorator`, `CcpStringDecorator`, `CcpTimeDecorator`, `CcpReflectionConstructorDecorator`, `CcpJsonRepresentation`, `AlreadyTransformedJson`, `CcpQueryExecutorDecorator`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 9 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **22** tipos (1,9% dos 1.167).

## Observações

- Não confundir com decorator de entidade (que é Infraestrutura para entidades de dados).
- Os `Consumer` auxiliares do pacote (`CcpStringBooleanCheck` e afins) contam como Outras interfaces.
