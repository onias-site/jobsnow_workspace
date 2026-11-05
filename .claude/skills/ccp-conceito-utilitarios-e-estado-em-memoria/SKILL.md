---
name: ccp-conceito-utilitarios-e-estado-em-memoria
description: Conceito "Utilitários e estado em memória" da taxonomia de tipos de classes Java do JobsNow. Classes auxiliares e de estado em memória (VisSkillDictionary, VisSkillsInText, JnEmailHtml, JnGroupers, JnSystemProperties, VisTelegram*). Use ao criar ou classificar um utilitário ou cache em memória.
---

# Utilitários e estado em memória

## Definição

Classes auxiliares que não são ação nem DSL: montagem de HTML de e-mail, mensagens, leitura de propriedades, dicionários e índices mantidos em memória, extração de dados de textos do Telegram e do WhatsApp, constantes.

## Exemplos

`VisSkillDictionary`, `VisSkillsInText`, `VisSkillWordsByInitials`, `JnEmailHtml`, `JnGroupers`, `JnSystemProperties`, `VisTelegramPositionText`, `CacheDeletionMarks`, `CcpOtherConstants`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 7 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **24** tipos (2,1% dos 1.167).

## Observações

- Reconhecida pela lista nominal `UTIL` do script.
- Classe que guarda dado é imutável (regra IMO); se o utilitário cresce em operações, ele vira decorator em `com.ccp.decorators` (regra DEW).
