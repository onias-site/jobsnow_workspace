# Endpoints e Swagger como decorators de entidade

Análise de 2026-10-19. Nada foi codificado.

**Pergunta.** As configurações de Swagger e de endpoint podem virar decorators de entidade, pensando num Spring Boot genérico
que receba os jars pelo classpath da linha de comando?

**Escopo.** Os 6 endpoints que `TabSkills.tsx` chama (API vis, porta 8081) e os 11 métodos de `JsRestApiLogin` (API js,
porta 8082). O `GET /login/{email}/erro` só existe para testar o handler de exceção e fica fora das contas. Sobram 16
endpoints.

## 1. Resposta curta

| # | Pergunta | Resposta |
|:-:|---|---|
| 1 | Viram decorators de entidade (itens do `CcpEntityDecoratorTypes`)? | Não, nenhum dos 16 |
| 2 | Viram configuração declarativa lida por um Spring Boot genérico? | Sim, os 16 |
| 3 | Essa configuração cabe na entidade protagonista? | Só em 8 dos 16 |
| 4 | Cabe no item do serviço (a constante do enum)? | Sim, nos 16 |
| 5 | O Swagger pode ser gerado? | A parte mecânica, sim; o texto livre, não |

Em resumo: a configuração inteira pode ser declarada. O lugar dela, porém, é o item do serviço, não a entidade. E ela é um
metadado lido pelo starter, não um decorator da cadeia.

## 2. Por que não é decorator de entidade

### 2.1 O endpoint executa um fluxo, não uma operação da entidade

Nenhum dos 16 endpoints é um `save`, `delete` ou `getOneById` puro de uma entidade. Cada um roda um item de serviço que,
antes de agir, confere outras entidades pela cadeia do `CcpGetEntityId` (de 1 a 8 verificações) e escolhe o status HTTP
pelo resultado. As duas buscas (#2 e #5 da seção 3) leem 2 e 5 entidades de uma vez e dizem em qual acharam o registro (o
campo `status`).

Os mais próximos de um CRUD são as desistências (#3 e #6): 404 quando não há pendente, a exclusão e o cancelamento do
chamado do operador. Elas virariam operação pura de entidade com duas mudanças:

- o cancelamento do chamado passa para um `@CcpAfterDeleteFromMainEntity` da entidade pendente;
- o 404 de "não existe" vira regra do endpoint genérico de exclusão.

Mesmo assim, o que muda é o serviço. A exposição continua não sendo decorator.

### 2.2 Nas entidades assíncronas, a cadeia roda depois da resposta

`@CcpEntityAsyncWriter` (prioridade 8) corta a cadeia e publica a operação na fila. Só o `FieldsValidator` (10) e o
`DataReadOnly` (9) rodam antes dele, ainda dentro da requisição. Os side effects `before` (7) e `after` (5) rodam no
consumidor da fila, depois que o cliente já recebeu a resposta.

Das 9 entidades protagonistas, 5 são assíncronas: `VisEntitySkillPending`, `VisEntitySkillFixHierarchyPending`,
`JnEntityLoginToken`, `JnEntityLoginTokenRequestResend` e `JnEntityLoginTokenRequestUnlock`. O login, a troca de senha e o
logout também escrevem pela fila (`JnFunctionMensageriaSender`). Um 403, 409 ou 429 lançado num decorator dessas entidades
nunca chegaria ao cliente HTTP.

O código já registra esse limite em dois lugares:

| # | Onde | O que o comentário diz |
|:-:|---|---|
| 1 | `VisServiceSkillFixHierarchy.FixSkillHierarchy` | repete fora da entidade a checagem de "já avaliado": "the save goes through the messaging ... the answer must tell them too" |
| 2 | `SuggestSkill` e `FixSkillHierarchy` | gravam o limite diário no serviço, "and not by the pending entity, because that one writes through the messaging" |

### 2.3 A regra ED não comporta exposição

Pela regra ED, decorator é o que muda o comportamento da entidade em create, read, update, transfer, copy ou delete, numa
posição da cadeia definida pelo catálogo. Publicar uma rota HTTP ou documentá-la não muda nenhuma dessas operações e não tem
posição na cadeia. É metadado lido por outro motor (o starter). É o mesmo caso de `@CcpEntityFieldPrimaryKey`, que o
`CcpEntityMetaData` lê sem que ela seja decorator.

## 3. Inventário

Caminhos relativos à base: vis `/resume/{email}/skills`, js `/login/{email}`. Nomes de entidade sem o prefixo
`VisEntity`/`JnEntity`/`JsEntity`.

| # | Método e caminho | Executa | Protagonista | C.C. |
|:-:|---|---|---|:-:|
| 1 | POST /hierarchy | FixSkillHierarchy | SkillFixHierarchyPending | vis |
| 2 | POST /hierarchy/search | GetSkillFixHierarchy | Pending + Fulfiled | vis |
| 3 | DELETE /hierarchy | DeleteSkillFixHierarchy | SkillFixHierarchyPending | vis |
| 4 | POST /suggestion | SuggestSkill | SkillPending | vis |
| 5 | POST /suggestion/search | GetSkillSuggestion | 5 entidades | vis |
| 6 | DELETE /suggestion | DeleteSkillSuggestion | SkillPending | vis |
| 7 | GET /{sessionToken} | JnBusinessValidateLogin | LoginSessionValidation | jn |
| 8 | POST / | ExecuteLogin | LoginSessionValidation | jn |
| 9 | POST /token | CreateLoginEmail | LoginEmail | jn |
| 10 | POST /token/request/unlocking | UnlockLoginToken | LoginTokenRequestUnlock | jn |
| 11 | POST /token/request/resending | ResendLoginToken | LoginTokenRequestResend | jn |
| 12 | HEAD /token | ExistsLoginEmail | LoginEmail | jn |
| 13 | DELETE /{sessionToken} | ExecuteLogout | LoginSessionValidation | jn |
| 14 | POST /pre-registration | SaveAnswers | LoginAnswers | js |
| 15 | POST /password | SavePassword | LoginPassword | jn |
| 16 | POST /token/language/{language} | CreateLoginToken | LoginToken | jn |

Os itens 1 a 6 são de `VisServiceSkillFixHierarchy` e `VisServiceSkillSuggestion`, e os itens 8 a 16 são de
`JsServiceLogin`. O #7 executa uma classe do jn, não um item de serviço.

## 4. Configuração de endpoint: o que pode ser declarado

| # | Elemento | Onde está hoje | Declarável? |
|:-:|---|---|:-:|
| 1 | Método e caminho | controller e interface OpenAPI (duplicado) | ✔ |
| 2 | Variável de caminho → campo do JSON | wrapper (e-mail, language) e controller (sessionToken) | ✔ |
| 3 | Valores de sessão (ip, userAgent, sessionToken) | `CcpPutSessionValuesRequestWrapper` | já genérico |
| 4 | E-mail inválido no caminho (400) | `CcpValidEmailFilter`, por prefixo de URL | ✔ |
| 5 | Validação de sessão (401) | filtro por padrão de URL | ✔ |
| 6 | O que executar | 1 linha no controller | ✔ |
| 7 | Validação do corpo (422) | classe com o nome do item (`JnService`) | já declarativa |
| 8 | Status e corpo da resposta | `CcpRestApiExceptionHandlerSpring` | já genérico |
| 9 | CORS | `@CrossOrigin` e cabeçalhos dos filtros | global |
| 10 | Injeção de dependências | `main` de cada starter | externalizar |
| 11 | Registro do erro não tratado | `main` de cada starter (`JnEntityJobsnowError`) | externalizar |
| 12 | Porta | linha de comando | ✔ |

Os 16 métodos de controller têm de 1 a 3 linhas. Eles só convertem o corpo, copiam uma variável de caminho para o JSON e
chamam `execute`: o #7 copia `sessionToken` como `sessionToken`, e o #13 copia como `token`. Nada nesses métodos impede a
declaração. O único ajuste é aceitar renomear a variável de caminho, ou mudar o #13 para `{token}`.

Hoje o e-mail e a language são extraídos por busca no texto da URL: o primeiro e-mail válido, e o segmento depois de
`language/`. Num registro por endpoint, o caminho declarado diz exatamente onde está cada variável.

## 5. Swagger: o que pode ser gerado

Volume atual: 741 linhas em 3 interfaces (`JsOpenApiLogin` 466, `VisOpenApiSkillSuggestion` 135,
`VisOpenApiSkillFixHierarchy` 140), com 16 operações e 83 respostas.

| # | Elemento | Gerado a partir de | Texto à mão? |
|:-:|---|---|:-:|
| 1 | Caminho, método e operationId | registro do endpoint | não |
| 2 | Tag (nome e descrição) | — | sim, 1 por serviço |
| 3 | Bloco "Path variables" (9 operações) | regras do campo de mesmo nome | não |
| 4 | Bloco "Request body fields" (15 operações) | classe de validação do item | não |
| 5 | Respostas 400/401/422/500 (15 das 83) | configuração do endpoint | não |
| 6 | Demais respostas (68 das 83) | o código, do enum de status | sim, a descrição |
| 7 | summary e "When does it occur? / What does it do?" | — | sim |
| 8 | Exemplos de JSON de resposta | — | sim, ou omitir |
| 9 | Título e versão da API | — | sim, 1 por API |
| 10 | Customizador de path params e swagger-ui | já idênticos nos 2 starters | não |

**Itens 3 e 4: o motor já existe.** `CcpJsonValidationRulesEngine.getRulesExplanation(Class)` (ccp) explica cada regra de
cada campo (`ruleName`, `ruleDescription`) e as regras globais. As anotações de campo trazem `minLength`, `maxLength`,
`regexValidation`, `allowedValuesEnum` e `exactLength`, que viram um JSON Schema de verdade (`minLength`, `maxLength`,
`pattern`, `enum`, `required`). Esse schema é melhor que o HTML que vai hoje dentro da `description`. Há outro ganho: com o
corpo tipado, o orval do front passaria a gerar o cliente tipado, em vez de `Map<String, Object>`.

**Campos injetados pelo servidor.** `userAgent`, `ip` e `email` aparecem como "Request body fields" nas 9 operações do login
que têm corpo. Só que o cliente não os manda: o wrapper os injeta. Um gerador que só lesse a classe de validação copiaria esse
erro. O starter genérico sabe o que injeta e pode documentar esses campos como cabeçalho ou caminho.

**A descrição da resposta pertence ao status, não ao endpoint.** Das 60 respostas do login, 22 repetem 4 textos:

| # | Texto (início) | Vezes |
|:-:|---|:-:|
| 1 | Invalid email format... | 8 |
| 2 | Token is locked... | 6 |
| 3 | User already logged in... | 4 |
| 4 | Password pending unlock... | 4 |
| | **Total** | **22** |

Os enums de status quase coincidem com os itens de serviço (`JnProcessStatusCreateLoginEmail`,
`JnProcessStatusExistsLoginEmail` e outros). Há três desvios:

| # | Desvio | Efeito na geração |
|:-:|---|---|
| 1 | `JnProcessStatusExecuteLogin` serve também a validação de sessão (os 401) | o login documentaria 401 que não produz |
| 2 | `JnProcessStatusUnlockLoginToken` serve também o reenvio | os textos de 409 e 429 diferem um pouco entre os dois |
| 3 | o vis usa `CcpProcessStatusDefault.CONFLICT` e `NOT_FOUND` | texto genérico onde hoje há texto específico |

## 6. Divergências do Swagger escrito à mão

Estas divergências mostram o que se perde por manter a documentação separada do código que executa.

| # | Divergência | Onde |
|:-:|---|---|
| 1 | `wordsHash`/`words` documentados no login e na senha; nenhuma classe fora do OpenAPI usa `wordsHash` | `JsOpenApiLogin` |
| 2 | `savePassword` documenta 423 "Weak password"; o fluxo não produz 423 (senha fraca cai na validação, 422) | `JsOpenApiLogin` |
| 3 | nenhum dos 10 endpoints do login documenta o 422 de validação | `JsOpenApiLogin` |
| 4 | as buscas justificam o POST porque "the session filter only validates the login when the request has a body"; desde 2026-10-06 o wrapper valida toda requisição | `VisOpenApiSkill*` |
| 5 | Javadocs de `unlockLoginToken` e `resendLoginToken` trocados no controller (o contrato foi corrigido em 2026-10-07, o controller não) | `JsRestApiLogin` |

O achado 49 (`LoginTokenRequestDocumentationTest`) é dessa família: o springdoc liga a documentação ao controller pelo nome do
método, e a documentação de dois endpoints ficou trocada. Quando a documentação e a execução são o mesmo elemento, essa
classe de defeito deixa de existir.

No item 4, continuar com POST pode ter outro motivo (corpo em GET não é padrão). O que ficou velho foi a justificativa
escrita.

## 7. Onde ancorar: entidade protagonista ou item do serviço

| # | Endpoint | Entidade: cabe | Entidade: não cabe | Item: cabe |
|:-:|---|:-:|:-:|:-:|
| 1 | POST /hierarchy | ✔ | | ✔ |
| 2 | POST /hierarchy/search | ✔ | | ✔ |
| 3 | DELETE /hierarchy | ✔ | | ✔ |
| 4 | POST /suggestion | ✔ | | ✔ |
| 5 | POST /suggestion/search | ✔ | | ✔ |
| 6 | DELETE /suggestion | ✔ | | ✔ |
| 7 | GET /{sessionToken} | ✔ | | ✔ |
| 8 | POST / | | ✔ | ✔ |
| 9 | POST /token | | ✔ | ✔ |
| 10 | POST …/unlocking | | ✔ | ✔ |
| 11 | POST …/resending | | ✔ | ✔ |
| 12 | HEAD /token | | ✔ | ✔ |
| 13 | DELETE /{sessionToken} | | ✔ | ✔ |
| 14 | POST /pre-registration | ✔ | | ✔ |
| 15 | POST /password | | ✔ | ✔ |
| 16 | POST …/language/{language} | | ✔ | ✔ |
| | **Total** | **8** | **8** | **16** |

**Por que 8 não cabem.** A entidade é do jn e o serviço é do js. Anotar a entidade com o serviço faria o jn importar o js,
o que a ordem ccp → jn → vis/jb/js proíbe. Também não dá para mudar as entidades de lugar:

- `LoginEmail`, `LoginPassword` e `LoginSessionValidation` ficaram no jn em 2026-10-17 porque classes do jn usadas pelo vis e
  pelo jb dependem delas;
- `LoginToken`, `LoginTokenRequestResend` e `LoginTokenRequestUnlock` são usadas pelo bot de suporte do jb
  (`JbSupportLoginTokenTypes`), e o jb não importa o js.

Levar o serviço para o jn desfaria o centro de custo js. Citar o serviço por nome de classe em texto contornaria a regra em
vez de cumpri-la.

**Outros custos da âncora na entidade, mesmo nas 8 em que cabe:**

| # | Custo | Detalhe |
|:-:|---|---|
| 1 | Várias rotas por entidade | anotação `@Repeatable`: 3 em LoginSessionValidation, 3 em cada Pending, 2 em LoginEmail |
| 2 | Protagonista arbitrária nas buscas | #2 lê 2 entidades e #5 lê 5 |
| 3 | Texto de Swagger no cabeçalho da entidade | as 741 linhas iriam para 9 entidades |
| 4 | `@ApiResponse` aninhada | proibida pela regra "nenhuma anotação aninhada" |
| 5 | Anotação do `io.swagger` em módulo de negócio | proibida pela regra ATP |

**Por que o item do serviço encaixa.** A estrutura de hoje já é 1 para 1 com ele:

| # | Hoje | No modelo por item |
|:-:|---|---|
| 1 | Controller (`VisRestApiSkillSuggestion`) | enum do serviço (`VisServiceSkillSuggestion`) |
| 2 | `@RequestMapping` da classe | anotação no enum: caminho base e tag |
| 3 | Método do controller | constante do enum |
| 4 | `@Operation` da interface | anotação na constante: summary e descrição |
| 5 | `@ApiResponses` | enums de status que a constante devolve |
| 6 | Classe de validação | a mesma, já achada pelo nome do item |

O Java aceita anotação em constante de enum, e a reflexão a lê por `Class.getField(nome).getAnnotation(...)`. As anotações
ficam no `ccp_commons_jobsnow`, sem Spring nem Swagger, e quem as traduz para Spring e OpenAPI é o starter. É a mesma divisão
dos módulos `ccp_db-*_elasticsearch`: a especificação no commons, a tecnologia no módulo de implementação.

O #7 executa `JnBusinessValidateLogin`, uma classe do jn. Anotá-la no jn publicaria a rota em todas as APIs, porque o jn está
em todo classpath (seção 8). Recrie em `JsServiceLogin` um item `ValidateLogin` que delega a ela; era esse o formato até
2026-10-17.

## 8. O Spring Boot genérico (desenho)

| # | Peça | O que faz |
|:-:|---|---|
| 1 | Módulo ccp | não importa jn, vis nem js; tudo chega por reflexão |
| 2 | Anotações no commons | regra ATP: o negócio depende só do commons |
| 3 | Descoberta | varre o classpath atrás dos serviços anotados |
| 4 | Lista de exposição | diz quais serviços publicar (linha de comando) |
| 5 | Registro | `RequestMappingHandlerMapping.registerMapping`, uma vez por rota |
| 6 | Despachante | corpo + caminho + sessão → validação de sessão → `execute(Map)` |
| 7 | OpenAPI | um `OpenApiCustomizer` monta as operações a partir do registro |
| 8 | Injeção de dependências | implementações escolhidas por propriedade |
| 9 | Erro não tratado | entidade de registro por propriedade |
| 10 | Classpath | `java -cp` ou `-Dloader.path` (PropertiesLauncher do Spring Boot) |
| 11 | Portas | 3 processos (8080/8081/8082) mantêm o front como está |

**A lista de exposição (peça 4) é obrigatória.** O jn é dependência do vis, do js e do jb, então está em todo classpath. Se o
starter publicasse tudo o que encontra, a API do vis publicaria também as rotas declaradas no jn. Classpath não é igual a
conjunto exposto.

**Segurança.** Não despache pelo nome de classe que vem da URL, como o consumidor de mensageria faz com `/{topic}`. Na fila
interna isso é aceitável. Numa API pública, instanciaria qualquer classe do classpath. A tabela de rotas sai só das
anotações lidas na subida, e rota desconhecida responde 404.

**Precedente.** O padrão "executar pelo nome da classe" já existe: `CcpMensageriaReceiver.getProcess` (ccp) recebe um
`CcpBusiness` ou um `CcpEntityConfigurator` mais a operação, e o bot do jb roda cada passo pelo nome da classe. O starter
genérico de REST é o mesmo padrão com a tabela de rotas fechada.

**Compatibilidade:**

| # | Ponto | Situação |
|:-:|---|---|
| 1 | operationId | 12 dos 16 coincidem com o nome do item em lowerCamel |
| 2 | Os 4 que não coincidem | todos do vis: SuggestSkill, FixSkillHierarchy, DeleteSkillFixHierarchy, GetSkillFixHierarchy |
| 3 | `swagger.json` do front | entrada do orval, só login e async: os 10 do login coincidem |
| 4 | `LoginTokenRequestDocumentationTest` | confere operationId e summary: continua passando |
| 5 | Variável de caminho inválida | hoje e-mail dá 400 (filtro) e language dá 422; validando o caminho, as duas dariam 400 |
| 6 | Telegram em ambiente local | o starter do js usa o local; o do vis manda de verdade; um starter único obriga a escolher |
| 7 | 401 nas buscas | o front trata 401 como "sem sugestão"; a validação de sessão por endpoint preserva isso |

Os 4 operationIds do vis precisam de um atributo próprio na anotação, ou da troca de nome. Não achei uso do cliente gerado
pelo orval no código do front hoje, mas o `swagger.json` e o `orval.config.cjs` estão lá.

## 9. Decisões

| # | Situação atual | Opções | Minha Recomendação |
|:-:|---|---|---|
| 1 | Endpoint em controller por centro de custo | a) entidade · b) item do serviço · c) manter controllers | b) item do serviço |
| 2 | Swagger escrito à mão, 741 linhas | a) tudo em anotação · b) gerar o mecânico · c) manter | b) gerar o mecânico |
| 3 | Texto de cada status repetido por endpoint | a) no endpoint · b) no item do enum de status | b) no status |
| 4 | Exposição implícita pelo módulo de API | a) tudo do classpath · b) lista na linha de comando | b) lista |
| 5 | Lugar da anotação no ccp | a) item do `CcpEntityDecoratorTypes` · b) anotação própria | b) anotação própria |
| 6 | Uma API por centro de custo | a) 3 processos · b) 1 processo | a) 3 processos |

1. **Item do serviço.** É a única âncora que cabe nos 16, respeita a ordem dos centros de custo e põe a documentação no
   mesmo elemento que executa. A entidade cabe em 8 e deixa as buscas com protagonista arbitrária. Manter os controllers não
   elimina os 3 módulos de API.
2. **Gerar o mecânico.** Gere caminho, método, operationId, parâmetros, schema do corpo e as respostas 400/401/422/500.
   Escreva à mão só a tag, o summary, a descrição ("When does it occur? / What does it do?") e o texto de cada status. As
   divergências da seção 6 vêm justamente do que hoje é escrito à mão.
3. **Texto no status.** Anote cada item do enum de status com a descrição dele, e deixe o endpoint dizer quais enums
   devolve. Separe os 2 enums compartilhados (seção 5) e crie status próprios no vis no lugar de `CONFLICT` e `NOT_FOUND`.
   Permita sobrescrever o texto por endpoint quando o sentido mudar.
4. **Lista de exposição.** Passe na linha de comando os serviços (ou pacotes) a publicar. Publicar tudo o que estiver no
   classpath expõe as rotas do jn em todas as APIs.
5. **Anotação própria.** Crie um conjunto de anotações de exposição, fora do catálogo de decorators: elas não mudam operação
   de entidade e não têm posição na cadeia. Siga as mesmas convenções: sem aninhamento, `value` quando o parâmetro é único,
   colaboradores de outro centro de custo como parâmetro (a validação de sessão como `Class`) e Javadoc do ccp com nomes
   neutros.
6. **Três processos.** O mesmo jar genérico, subido 3 vezes com classpath, lista de exposição e porta diferentes, mantém as
   portas que o front e a suíte de testes usam. Um processo único exige mudar o front (`TabSkills.tsx` fixa a 8081, o login
   usa a 8082).

## 10. Arquivos lidos

| # | Arquivo |
|:-:|---|
| 1 | `jn_frontend_calistrato-react/.../tabs/TabSkills/TabSkills.tsx` |
| 2 | `js_rest-api_spring_jobsnow_dependency-chooser/.../JsRestApiLogin.java`, `JsOpenApiLogin.java`, `JsRestApiSpringStarter.java` |
| 3 | `vis_rest-api_spring_jobsnow_dependency-chooser/.../VisRestApiSkillSuggestion.java`, `VisRestApiSkillFixHierarchy.java` |
| 4 | `vis_rest-api_spring_jobsnow_dependency-chooser/.../VisOpenApiSkillSuggestion.java`, `VisOpenApiSkillFixHierarchy.java`, `VisRestApiSpringStarter.java` |
| 5 | `ccp_rest-api-handler-exception_spring/.../CcpPutSessionValuesAndExecuteTaskFilter.java`, `CcpPutSessionValuesRequestWrapper.java`, `CcpValidEmailFilter.java`, `CcpRestApiExceptionHandlerSpring.java` |
| 6 | `js_business_jobsnow/.../JsServiceLogin.java` e as 9 classes de validação de `com.js.services` |
| 7 | `vis_business_jobsnow/.../VisServiceSkillSuggestion.java`, `VisServiceSkillFixHierarchy.java` |
| 8 | `ccp_commons_jobsnow/.../CcpEntityDecoratorTypes.java`, `CcpEntity.java`, `CcpEntityOperationType.java`, `CcpEntityConfigurator.java`, `CcpService.java` |
| 9 | `ccp_commons_jobsnow/.../CcpJsonValidationRulesEngine.java`, `CcpJsonFieldValidatorInterface.java`, `CcpMensageriaReceiver.java`, `CcpProcessStatus.java` |
| 10 | Entidades: `VisEntitySkillPending`, `VisEntitySkillFixHierarchyPending`, `JnEntityLoginEmail` e os cabeçalhos das outras 6 |
| 11 | `JnBusinessValidateLogin`, `JnProcessStatusExecuteLogin`, `JnProcessStatusUpdatePassword`, `VisProcessStatusSuggestSkill`, `JnJsonCommonsFields`, `VisJsonCommonsFields`, `JnLanguage` |
| 12 | `JnMensageriaConsumerGcpPubSubPushSpringStarter`, `JbSupportLoginTokenTypes`, `LoginTokenRequestDocumentationTest`, `swagger.json` e `orval.config.cjs` do front |
