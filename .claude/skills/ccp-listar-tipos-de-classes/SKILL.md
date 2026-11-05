---
name: ccp-listar-tipos-de-classes
description: Lista os tipos de classes Java de produção do JobsNow (Anotações, Business, Fields, Entidades de dados, Especificação / implementação e as demais categorias da taxonomia) com a quantidade e a porcentagem de cada uma, numa grade com bordas ordenada da maior para a menor. Também detalha os tipos de uma categoria e mostra os conflitos (tipos que atendem duas categorias e qual venceu). Uso - /ccp-listar-tipos-de-classes, /ccp-listar-tipos-de-classes detalhe <categoria>, /ccp-listar-tipos-de-classes conflitos.
disable-model-invocation: true
---

# Listar os tipos de classes Java

Classifica cada tipo de `src/main` do workspace (menos `ccp_rest-api-tests_jobsnow`, `documentation`, o front end e `target`) numa **única** categoria e imprime a contagem. Só lê o código-fonte.

## Passos

1. Ler `$ARGUMENTS`:
   - vazio → tabela geral;
   - `detalhe <texto>` → `--detalhe "<texto>"` (parte do nome da categoria basta, sem acento: `fields`, `bot`, `enum`);
   - `conflitos` → `--conflitos`.
2. Rodar (a partir de qualquer pasta):
   ```bash
   python -X utf8 "C:/eclipse-workspaces/ccp/.claude/skills/ccp-listar-tipos-de-classes/scripts/tipos_de_classes.py" [opção]
   ```
3. Mostrar a grade exatamente como saiu, dentro de um bloco de código.
4. Se aparecer a linha `Sem categoria:`, apontar os tipos e propor a categoria de cada um (ver "Manutenção").

## Regra da categoria única

Um tipo pode atender a mais de um critério (todo `CcpBusiness` também é `CcpJsonFieldName`, por exemplo). Ele conta só para a **primeira** categoria da ordem abaixo que atender. Essa ordem foi decidida pelo usuário em 2026-11-04:

| Ordem | Categoria | Critério | Skill de conceito |
|---:|---|---|---|
| 1 | Entidades de dados | tem `public static final CcpEntity ENTITY` | `ccp-conceito-entidades-de-dados` |
| 2 | Business | implementa `CcpBusiness`, direta ou indiretamente | `ccp-conceito-business` |
| 3 | Infraestrutura para entidades de dados | `CcpEntity` e todos os seus descendentes, e `CcpBulkItem` | `ccp-conceito-infraestrutura-para-entidades` |
| 4 | DSLs fluentes | lista `DSL` do script | `ccp-conceito-dsls-fluentes` |
| 5 | Motores e infraestrutura do framework | lista `ENGINE` | `ccp-conceito-motores-do-framework` |
| 6 | Infraestrutura web e de mensageria | lista `WEB` | `ccp-conceito-infraestrutura-web-e-mensageria` |
| 7 | Utilitários e estado em memória | lista `UTIL` | `ccp-conceito-utilitarios-e-estado-em-memoria` |
| 8 | Configuração e conversa do bot | nome termina em `BotConfiguration`, `Conversation`, `ReviewMessage`, `BotCommands`, `Steps`, `AnswerType` (inclusive enums), mais os da lista `BOT` | `ccp-conceito-configuracao-e-conversa-do-bot` |
| 9 | Decorators | implementa `CcpDecorator`, nome termina em `Decorator`, `CcpJsonRepresentation` | `ccp-conceito-decorators` |
| 10 | Anotações | `@interface` | `ccp-conceito-anotacoes` |
| 11 | Exceções | descende de `Throwable` | `ccp-conceito-excecoes` |
| 12 | Provedores de DI | implementa `CcpInstanceProvider` | `ccp-conceito-provedores-de-di` |
| 13 | Especificação / implementação | interface de `com.ccp.especifications` ou quem a implementa | `ccp-conceito-especificacao-e-implementacao` |
| 14 | Fields | implementa `CcpJsonFieldName` | `ccp-conceito-fields` |
| 15 | Ignorados | aspectos, controllers, interfaces OpenAPI, starters Spring, classes com `main` | — |
| 16 | Enum complexo | enum que implementa alguma interface | `ccp-conceito-enum-complexo` |
| 17 | Enum simples | enum que não implementa interface | `ccp-conceito-enum-simples` |
| 18 | Esquemas de validação de entrada | classe sem supertipo e sem métodos, só com campos `@CcpJsonFieldValidator*` / `@CcpJsonCopyFieldValidationsFrom` | `ccp-conceito-esquemas-de-validacao-de-entrada` |
| 19 | Outras interfaces | interface que sobrou, ou classe que implementa interface que sobrou (lambdas extraídas pela regra MLC) | `ccp-conceito-outras-interfaces` |

Em `conflitos`, coincidir com "Outras interfaces" não conta como conflito: ela é a categoria de sobra.

## Manutenção

As categorias 4 a 7 (e parte da 8) dependem de listas nominais no topo do script (`DSL`, `ENGINE`, `WEB`, `UTIL`, `BOT`, `ENTITY_INFRA`). Uma classe nova desses tipos cai em "Outras interfaces" ou em "Sem categoria" até entrar na lista. Ao criar uma, acrescente o nome à lista certa. Se mudar uma prioridade ou criar uma categoria, atualize o script, esta tabela e a skill de conceito correspondente.

Fotografia de 2026-11-04: 1.167 tipos. Anotações 357, Business 181, Fields 89, Entidades 83, Especificação / implementação 59, Outras interfaces 57, DSLs 39, Enum simples 39, Ignorados 36, Exceções 34, Bot 32, Infraestrutura de entidades 26, Utilitários 24, Motores 22, Decorators 22, Web/mensageria 22, Enum complexo 20, Provedores de DI 16, Esquemas de validação 9.
