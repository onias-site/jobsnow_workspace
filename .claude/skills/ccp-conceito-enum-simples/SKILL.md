---
name: ccp-conceito-enum-simples
description: Conceito "Enum simples" da taxonomia de tipos de classes Java do JobsNow. Enum que não implementa nenhuma interface (opções do framework como CcpEntityExpurgableOptions, CcpHttpMethods; domínio como VisSeniorityType, VisSkillSuggestionStatus). Use ao criar ou classificar um enum sem interface.
---

# Enum simples

## Definição

Enum que não implementa nenhuma interface: opções e tipos do framework e valores de domínio (situações, tipos, senioridade).

## Exemplos

`CcpEntityExpurgableOptions`, `CcpEntityOperationType`, `CcpHttpMethods`, `TimeOptions`, `JnTicketQuotaGroups`, `VisSeniorityType`, `VisSkillSuggestionStatus`, `SalaryType`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 17 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **39** tipos (3,3% dos 1.167).

## Observações

- Os enums de bot `*BotCommands`, `*Steps` e `*AnswerType` não contam aqui: vão para Configuração e conversa do bot.
- Decisão que dependa do enum vira método abstrato dele (regra EAD), e então ele continua simples enquanto não implementar interface.
