---
name: ccp-conceito-enum-complexo
description: Conceito "Enum complexo" da taxonomia de tipos de classes Java do JobsNow. Enum que implementa alguma interface fora das categorias de maior prioridade (mensagens JnSystemMessage, CcpJsonValidatorDefaults, CcpTemplateFunctions, JsonConditions). Use ao criar ou classificar um enum com comportamento por interface.
---

# Enum complexo

## Definição

Enum que implementa alguma interface e não foi capturado por uma categoria de maior prioridade. A maioria implementa `JnSystemMessage` (os textos ao usuário semeados por idioma); os demais implementam interfaces funcionais ou do validador.

## Exemplos

`VisTelegramSystemMessages`, `JsPrivacyPolicyMessages`, `JbLanguageNames`, `CcpJsonValidatorDefaults`, `CcpJsonFieldDefaultTypes`, `CcpTemplateFunctions`, `JsonConditions`, `JnMessageSenderExceptionHandler`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 16 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **20** tipos (1,7% dos 1.167).

## Observações

- Perde para Business, Fields, Provedores de DI e Especificação quando o enum implementa as interfaces delas.
- Decisão sobre enum vai para um método abstrato do enum (regra EAD).
