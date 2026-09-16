---
name: centralizar-field-names
description: Troca referências a itens de enum de field name locais (Fields de entidade, JsonFieldNames de endpoint, enums validadores) pelos enums centralizadores globais de cada centro de custo (JnJsonCommonsFields, JnJsonInstantMessengerFields, VisJsonCommonsFields). Use quando pedirem para "centralizar field names", "usar o enum centralizador", "trocar X.Fields.campo por JnJsonCommonsFields.campo" ou ao criar/revisar código que declare nomes de campo já existentes nos centralizadores.
---

# Centralizar field names nos enums globais por centro de custo

Sempre que um nome de campo JSON já existe em um enum centralizador global, o código
deve referenciar o centralizador — nunca o enum local homônimo.

```java
// ANTES
recordFromUnionAll.putSameValueInManyFields(command,
        JbEntityBotCommandStep.Fields.stepName, JbEntityBotCommand.Fields.commandName)
    .put(JbEntityBotExplanation.Fields.language, language);

// DEPOIS
recordFromUnionAll.putSameValueInManyFields(command,
        JnJsonInstantMessengerFields.stepName, JnJsonInstantMessengerFields.commandName)
    .put(JnJsonCommonsFields.language, language);
```

Como `CcpJsonFieldName.getValue()` devolve `name()`, a troca é semanticamente neutra:
a chave gravada no JSON continua idêntica. O ganho é ter uma única fonte de verdade
por nome de campo.

## Os centralizadores

| Enum | Arquivo | Domínio |
|------|---------|---------|
| `JnJsonCommonsFields` | `jn_business_jobsnow/.../com/jn/json/fields/validation/` | campos comuns a todo o JobsNow |
| `JnJsonInstantMessengerFields` | mesma pasta | campos de mensageria instantânea (Telegram/bots) |
| `VisJsonCommonsFields` | `vis_business_jobsnow/.../com/vis/json/fields/validation/` | campos do centro de custo VIS |

**Não existe centralizador Jb.** O centro de custo Jb (`jb_business_jobsnow`,
`jb_instant-messenger-listener_...`) usa os enums Jn.

## Regra de escolha do alvo

1. Se o arquivo está em módulo `vis_*` **e** o nome existe em `VisJsonCommonsFields` → usa ele.
2. Senão, se o nome é de mensageria **e** existe em `JnJsonInstantMessengerFields` → usa ele.
   Campos de mensageria: `stepName`, `commandName`, `botName`, `chatId`, `botToken`,
   `instantMessageType`, `caption`, `fileName`, `contentType`, `message`,
   `moreParameters`, `templateId`.
3. Senão, se existe em `JnJsonCommonsFields` → usa ele.
4. Senão → **não troca** (ver "Quando NÃO trocar").

Confirmação independente da regra: quando a constante do enum local traz
`@CcpJsonCopyFieldValidationsFrom(X.class)`, `X` é exatamente o alvo correto.
Rode `scripts/copyfrom.js` para listar esse mapeamento a partir do código real —
é a melhor fonte de verdade quando houver dúvida.

## Quando NÃO trocar

- **Módulos `ccp_*`** — são a camada 0/1 do framework e não dependem de `jn_business`
  nem de `vis_business`. Trocar quebraria a ordem de dependências.
- **Projeto de testes** (`ccp_rest-api-tests_jobsnow`) — fora de escopo por decisão do usuário.
- **Alvo inalcançável pelo módulo**: `jb_*` não depende de `vis_business`, então
  `listSize`, `from`, `title` etc. permanecem no enum local dentro de Jb.
- **Enums que não são de field name**, mesmo com constante homônima:
  - `CcpLocalInstances` (provedores de DI: `email`, `bucket`, …);
  - `JbDefaultBotCommandStep` (constantes com corpo — são comandos de bot, não campos);
  - `JnJsonTransformersFieldsEntityDefault` / `...DoNothing` (transformadores casados
    por reflexão via `@CcpEntityFieldsTransformer`).

## Manter ou remover a declaração local

Depois de trocar os **usos**, a declaração do item no enum local segue esta regra
(decidida pelo usuário, não derivável do código):

- **MANTÉM** quando o enum é consumido por reflexão pelo framework:
  1. enums `Fields` de entidade (`com.jb.entities`, `com.jn.entities`, `com.vis.entities`) —
     definem as colunas do banco;
  2. **descritores de validação** — heurística: *algum item do enum tem anotação*
     (`@CcpJsonFieldTypeX`, `@CcpJsonFieldValidatorRequired`, `@CcpJsonCopyFieldValidationsFrom`,
     `@CcpEntityFieldPrimaryKey`). São alcançados por `getJsonValidationClass()`,
     `jsonValidation = X.class`, `classReferenceWithTheFields = X.class` ou `.values()`.
     Remover apagaria regras de validação silenciosamente.
- **REMOVE** nos demais (enums planos de nomes de campo) — e some com o enum se ficar vazio.
  **Antes de remover, confira se o projeto de testes referencia a constante**; se
  referenciar, mantenha-a (o projeto de testes não pode ser editado) e avise o usuário.

## Procedimento

```bash
cd .claude/skills/centralizar-field-names/scripts
node survey.js enums.json     # cataloga todos os enums e suas constantes
node analyze.js               # lista enums com constantes homônimas dos centralizadores
node copyfrom.js              # confirma campo -> centralizador pelas anotações reais
node rewrite.js               # DRY RUN: mostra as trocas e os imports afetados
node rewrite.js --apply       # aplica
```

`rewrite.js` já cuida de: pular comentários e literais de string, adicionar os
`import` necessários, remover imports que ficaram sem uso e ignorar os casos da
lista negra. Depois de aplicar:

1. Remova manualmente as declarações locais elegíveis (seção acima).
2. Se algum centralizador ainda não implementa `CcpJsonFieldName`, adicione
   (`JnJsonInstantMessengerFields` precisou disso) — sem isso não compila em `put(...)`.
3. Rode `node rewrite.js` de novo: só devem sobrar linhas `SKIP` esperadas.

## Verificação

```bash
mvn -o install -DskipTests            # NÃO use "clean": o lock do Eclipse em
                                      # target/classes/builddef.lst faz o clean falhar
mvn -o test -pl ccp_rest-api-tests_jobsnow
```

Baseline esperado da suíte: **0 failures**; os erros restantes são pré-existentes e
ficam todos em `com.jn.rest.api` (Connection refused na 8080) e `com.jn.services.login`.
Qualquer erro fora desses dois pacotes é regressão.

Faça sempre backup antes de aplicar (`node scripts/backup.js`) — o repositório não é git.
Ao final, compare a árvore com o backup e reverta arquivos cuja única diferença seja
espaço em branco: churn cosmético não faz parte da tarefa.
