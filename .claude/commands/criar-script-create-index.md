# Criar Script de Create Index do Elasticsearch

Gera o arquivo de criação do índice do Elasticsearch correspondente a uma classe configuradora de entidade (`CcpEntityConfigurator`), a partir do enum `Fields` declarado nela.

Este é o script consumido por `CcpRandomScripts.createEntities(systemName)` → `CcpDbRequester.createTables(...)` → `ElasticSearchDbRequester.executeDatabaseSetup(...)`, que faz `DELETE` + `PUT` do índice usando o conteúdo do arquivo como body.

## Argumento esperado

`$ARGUMENTS` é a classe Java responsável pela entidade — nome simples (`JbEntityBotUpdateId`), nome qualificado (`com.jb.entities.JbEntityBotUpdateId`) ou caminho do arquivo `.java`. Se vier mais de uma, gerar um script por classe.

## Passos

1. Ler a classe Java informada. Ela deve implementar `CcpEntityConfigurator` e declarar `public static enum Fields implements CcpJsonFieldName`. Se não implementar, é entidade virtual (ignorada pelo setup) — avisar e parar.

2. Derivar o **nome da entidade** aplicando a mesma regra de `CcpEntityFactory.mainEntityNameProducer`: converter o simple name para snake_case e cortar tudo até depois de `entity_`.
   - `JbEntityBotUpdateId` → `jb_entity_bot_update_id` → `bot_update_id`

3. Derivar o **sistema** pelo prefixo do nome da classe antes de `Entity` (`Jn`, `Jb`, `Vis`), em minúsculas. O arquivo é gravado em:

   ```
   ccp_rest-api-tests_jobsnow/documentation/<sistema>/database/elasticsearch/scripts/entities/create/<nome-da-entidade>
   ```

   Sem extensão — o nome do arquivo é exatamente o nome da entidade (`ElasticSearchDbRequester.getScriptToCreateEntity`).

4. Se o arquivo já existir, ler antes e comparar: reportar as diferenças ao usuário em vez de sobrescrever silenciosamente.

5. Mapear **cada constante do enum `Fields`** para uma propriedade do mapping, usando as anotações de tipo do campo:

   | Anotação no campo | Tipo no mapping |
   |---|---|
   | `@CcpJsonFieldTypeNumber`, `@CcpJsonFieldTypeNumberInteger`, `@CcpJsonFieldTypeNumberUnsigned` | `long` |
   | `@CcpJsonFieldTypeBoolean` | `boolean` |
   | `@CcpJsonFieldTypeNestedJson` | `{ "dynamic": "true", "properties": {} }` |
   | `@CcpJsonFieldTypeString` / `@CcpJsonFieldTypeCustom` / sem anotação de tipo | `keyword` |
   | Texto livre e longo (mensagens, stack traces, request/response, descrições) | `text` |

   - `@CcpEntityFieldPrimaryKey` e `@CcpJsonFieldValidatorRequired` **não** alteram o tipo — chave primária é sempre `keyword` (ou `long`, se numérica).
   - `@CcpJsonFieldValidatorArray` **não** muda nada: no Elasticsearch qualquer campo já aceita lista do próprio tipo (ver `allowedUser` em `bot_allowed_user`).
   - Quando o tipo vier de `@CcpJsonCopyFieldValidationsFrom(XxxFields.class)`, abrir a classe de validações referenciada e ler as anotações do campo homônimo lá.
   - Na dúvida entre `keyword` e `text`: valores usados em filtro/igualdade/chave → `keyword`; conteúdo para leitura humana → `text`.

6. Escrever o arquivo com indentação por tabulação, seguindo o formato:

   ```json
   {
   	"mappings": {
   		"dynamic": "strict",
   		"properties": {
   			"<campo>": {
   				"type": "<tipo>"
   			}
   		}
   	}
   }
   ```

7. Conferir antes de encerrar: o conjunto de propriedades do script bate **exatamente** com as constantes do enum `Fields` — nem a mais, nem a menos.

8. Reportar ao usuário o caminho do arquivo criado, o conteúdo gerado e a justificativa de cada tipo escolhido.

## Restrições

- `"dynamic": "strict"` é obrigatório. `ElasticSearchDbRequester.validateEntityFields` lança `CcpErrorDbUtilsIncorrectEntityFields` se for qualquer outro valor.
- O mapping precisa cobrir exatamente os campos da entidade. Campo no script e não na classe, ou na classe e não no script, quebra o setup com a mesma exceção (os erros vão para `c:\logs\mappingJnEntitiesErrors.json`).
- Entidades com `@CcpEntityTwin` **não** precisam de um segundo arquivo: `recreateEntityTwin` reaproveita o mesmo script para o índice gêmeo.
- Não incluir bloco `settings`, `aliases` nem `_source` — nenhum script existente usa, e o body é enviado tal e qual no `PUT`.
- Não alterar a classe Java. Se o enum `Fields` estiver inconsistente (ex.: `@CcpEntityFieldsValidator` apontando para as `Fields` de outra entidade), apenas avisar.
- Esta skill gera **somente o script**. Para criar a entidade completa (classe Java + script, agnóstico de banco), use a skill `criar-entidade`.
