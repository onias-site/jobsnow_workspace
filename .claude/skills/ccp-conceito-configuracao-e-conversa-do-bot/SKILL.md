---
name: ccp-conceito-configuracao-e-conversa-do-bot
description: Conceito "Configuração e conversa do bot" da taxonomia de tipos de classes Java do JobsNow. Classes e enums que configuram e conduzem os comandos dos bots de suporte - *BotConfiguration, *Conversation, *Answer, *ReviewMessage, enums *BotCommands, *Steps, *AnswerType, JnBotConfigurationSeeds. Use ao criar ou classificar a configuração de um comando de bot.
---

# Configuração e conversa do bot

## Definição

Classes e enums que configuram e conduzem os comandos dos bots de suporte: a configuração (comando, passos, nomes, textos) que vai para as entidades `JnEntityBotCommand*` pelo `JnBotConfigurationSeeds`, a conversa com o operador, as respostas e as mensagens de revisão. Inclui os enums de comandos, de passos e de tipos de resposta (decisão de 2026-11-04).

## Exemplos

`JsSupportContactUsBotConfiguration`, `VisSupportSkillFixHierarchyConversation`, `JsSupportContactUsAnswer`, `VisSkillSuggestionReviewMessage`, `JnBotConfigurationSeeds`, `JbSupportBotCommands`, `JsSupportContactUsSteps`, `VisSupportSkillFixHierarchyAnswerType`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 8 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **32** tipos (2,7% dos 1.167).

## Observações

- Vence Enum simples: os 13 enums `*BotCommands` / `*Steps` / `*AnswerType` contam aqui.
- O comando pertence ao centro de custo dos dados em que trabalha; os passos são business executados pelo nome da classe (esses contam como Business).
