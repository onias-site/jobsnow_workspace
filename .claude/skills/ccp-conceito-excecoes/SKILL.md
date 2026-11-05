---
name: ccp-conceito-excecoes
description: Conceito "Exceções" da taxonomia de tipos de classes Java do JobsNow. Classes que descendem de Throwable (CcpErrorFlowDisturb, CcpErrorJson*, CcpNullParameterException). Use ao criar ou classificar uma exceção do JobsNow.
---

# Exceções

## Definição

Classes de primeiro nível que descendem de `Throwable`. Exceções usadas só dentro do arquivo que as declara ficam aninhadas (regra OTF) e não entram na contagem. `RuntimeException` genérica vira exceção de negócio.

## Exemplos

`CcpErrorFlowDisturb`, `CcpErrorJsonInvalid`, `CcpErrorJsonFieldNotFound`, `CcpErrorFileIsMissing`, `CcpNullParameterException`, `CcpNullReturnException`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 11 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **34** tipos (2,9% dos 1.167).

## Observações

- Mensagens de exceção em inglês; mensagem ao usuário final só via `JnEntitySystemMessage`.
