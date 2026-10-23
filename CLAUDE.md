# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**jobsnow** is a multi-module Java backend framework paired with a legacy React frontend. The backend is built around a custom decorator/DI pattern framework with Elasticsearch as the primary database. All 27 modules live together under a single aggregator `pom.xml` at the root and are managed as one Eclipse workspace (`C:\eclipse-workspaces\ccp`), each module being a separate Eclipse project.

## Module Structure

The root `pom.xml` is an aggregator (not a parent — modules keep their own `<parent>` declarations). Build order is encoded in the module list. A module's layer is the length of its longest chain of internal dependencies down to `ccp_commons_jobsnow`.

| Layer | Module | Purpose |
|-------|--------|---------|
| 0 | `ccp_commons_jobsnow` | Core framework: decorators, DI, entity system, query builders |
| 1 | `ccp_json_gson` | JSON serialization via Gson 2.7 |
| 1 | `ccp_cache_gcp-memcache` | Cache via GCP Memcache |
| 1 | `ccp_cron-tasks_jobsnow` | Scheduled/cron tasks |
| 1 | `ccp_db-bulk_elasticsearch` | Elasticsearch bulk operations |
| 1 | `ccp_db-crud_elasticsearch` | Elasticsearch CRUD |
| 1 | `ccp_db-utils_elasticsearch` | Elasticsearch utilities |
| 1 | `ccp_email_sendgrid` | Email via SendGrid |
| 1 | `ccp_file-bucket_gcp` | File storage via GCP |
| 1 | `ccp_http_apache-mime` | HTTP client via Apache MIME |
| 1 | `ccp_instant-messenger_telegram` | Telegram messaging |
| 1 | `ccp_main-authentication_gcp-oauth` | GCP OAuth authentication |
| 1 | `ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser` | PubSub pull consumer |
| 1 | `ccp_mensageria-sender_gcp-pubsub` | PubSub message sender |
| 1 | `ccp_password_mindrot` | Password hashing via BCrypt |
| 1 | `jn_business_jobsnow` | Core jobsnow business logic |
| 1 | `ccp_rest-api-handler-exception_spring` | Spring Boot exception handler (has own Spring parent) |
| 2 | `ccp_db-query_elasticsearch` | Elasticsearch query builder (depends on `ccp_json_gson`) |
| 2 | `vis_business_jobsnow` | Visualization business logic (depends on `jn_business_jobsnow`) |
| 2 | `jb_business_jobsnow` | BackOffice business logic and the bot engine (depends on `jn_business_jobsnow`; does not import vis) |
| 2 | `js_business_jobsnow` | JobsNow System business logic: the login service, the login entities (`JsEntityLogin*`, indices `js_login_*`), the session validator seeded in `jn_session_validator` and the support bot command `solveLoginTokenTicket` (depends on `jn_business_jobsnow`; does not import vis or jb) |
| 3 | `ccp_mocking_jobsnow` | Test mocks and DI wiring (depends on `ccp_db-query_elasticsearch`) |
| 4 | `jb_instant-messenger-listener_jobsnow_dependency-chooser` | BackOffice bot listener (brings `vis_business_jobsnow` and `js_business_jobsnow` to the classpath: the bot runs their steps by class name) |
| 4 | `jn_mensageria-consumer_gcp-pubsub-push-spring_dependency` | PubSub push consumer / Spring Boot app (has own Spring parent) |
| 4 | `js_rest-api_spring_jobsnow_dependency-chooser` | JobsNow System REST API / Spring Boot app (login and its Swagger, port 8082) |
| 4 | `vis_rest-api_spring_jobsnow_dependency-chooser` | Visualization REST API / Spring Boot app (port 8081; brings `js_business_jobsnow` to the classpath: it validates the session with the business seeded in `jn_session_validator`, run by class name through `JnBusinessValidateSession`) |
| 5 | `ccp_rest-api-tests_jobsnow` | Integration/API test suite (depends on every module above) |

## Repository Layout

This workspace is **not** a monorepo. Every module directory is its own git repository (28 of them, counting `jn_frontend_calistrato-react`, which is not a Maven module). Retired modules are kept as plain source under `ccp_rest-api-tests_jobsnow/documentation/` (the legacy frontend in `jn/frontend/legado`, `ccp_text-extractor_apache-tika` in `ccp/text-extractor_apache-tika`, with a git bundle of its history). Above them sits an umbrella repository for the workspace root itself:

- **`onias-site/jobsnow_workspace`** versions only what is shared by every project: the aggregator `pom.xml`, the `.bat` scripts, this `CLAUDE.md`, `.claude/` (slash commands and skills), `documentation/`, and the root-level notes.
- Its `.gitignore` excludes **every directory at the root** through a single `/*/` rule, so a new module is left out automatically with no edit needed; only `.claude/` and `documentation/` are re-included. Eclipse's `.metadata/` (~300 MB of machine-specific state) and `.claude/settings.local.json` are excluded as well.

Two scripts at the root drive all repositories at once. Both handle the workspace repository first, then every module repository beneath it:

```bash
fazPullEmTodosProjetosLocais.bat   # git reset --hard + git pull in each repository
fazPushEmTodosProjetosLocais.bat   # asks for one commit message, then add/commit/push in each repository
```

Both anchor themselves to the script's own directory, so they work from any working directory. Note that the pull script resets hard: uncommitted work in any repository — the workspace root included — is discarded.

## Build & Run Commands

### Java (Maven) — from the root `jobsnow/` directory

```bash
# Install all modules to local .m2 (required on first setup and after any module change)
mvn clean install

# Build without running tests
mvn clean package -DskipTests

# Run all tests
mvn test

# Run tests for a single module
mvn test -pl ccp_rest-api-tests_jobsnow

# Run a single test class
mvn test -pl ccp_rest-api-tests_jobsnow -Dtest=ClassName
```

### Frontend (in `documentation/jn/frontend/legado/`)

```bash
npm install
npm run dev        # Dev server on port 2200
npm run build-dev  # Dev build
npm run build      # Production build
npm start          # Start Node.js server
```

## Core Architecture

### Custom Framework (ccp_commons_jobsnow)

**Decorator Pattern** — Everything wraps a target type. Base class is `CcpDecorator<T>`, with specializations:
- `CcpJsonRepresentation` — the central value object; a map-like JSON container that flows through the entire system
- `CcpCollectionDecorator`, `CcpStringDecorator` — typed wrappers with utility methods
- `CcpReflectionConstructorDecorator`, `CcpReflectionFieldDecorator` — reflection utilities

**Business Logic** — `CcpBusiness` implements `Function<CcpJsonRepresentation, CcpJsonRepresentation>` with built-in validation via `validate()`. All business operations accept and return `CcpJsonRepresentation`.

**Dependency Injection** — `CcpDependencyInjection` provides interface-to-implementation binding at runtime. Tests wire real implementations; production may substitute mocks or cloud-specific implementations.

**Database Layer** — `CcpCrud` interface backed by Elasticsearch:
- `CcpQuery` / `CcpQueryBool` / `CcpQueryAggregations` — fluent query builder
- `CcpBulkExecutor` — bulk CRUD with pluggable handlers
- Schema definitions live in `documentation/jb/database/elasticsearch/scripts/entities/`
- Local logs go to `c:/logs/`

### Testing

Tests extend template base classes (`JnTemplateDeTestes`, `VisTemplateDeTestes`, `BaseTest`) that:
1. Bootstrap DI with real implementations
2. Load Elasticsearch schema from documentation scripts
3. Provide HTTP testing utilities (local APIs: login on 8082, vis on 8081; the jn API was removed on 2026-10-22)
4. Log full request/response for debugging

Business test class names follow English BDD-style conventions (e.g., `OnEnteringPasswordRegistrationScreen`, `PasswordLoginScreen`).

### Frontend

Legacy React + Redux stack (React 15–16, Webpack 2, Bootstrap 3). Deployed to Google App Engine. State managed via Redux + redux-thunk; routing via react-router 3. Chart.js, Highcharts, and D3 used for data visualization.

## Key Conventions

- The project is internationalizable: class, method, variable and field names, Javadoc, comments, OpenAPI texts and exception messages are written in English. Local variables get names that describe the value (`jsonWithInstantMessageType`, never `put10`). User-facing message templates are seeded per `JnLanguage` (Portuguese and English records side by side). Persisted field names, JSON keys and URL paths are contracts and are not renamed for translation purposes.
- Field names in JSON are defined as enums and passed to `CcpJsonRepresentation` accessors — avoid bare string keys.
- Cost centers follow a strict dependency order: **ccp → jn → vis/jb/js**. A `com.ccp` class must never import `com.jn`, `com.vis`, `com.jb` or `com.js`; a `com.jn` class must never import `com.vis`, `com.jb` or `com.js`. `ccp_rest-api-tests_jobsnow` is the only module exempt from the rule. Module prefix and root package always agree (`ccp_*` → `com.ccp`, `jn_*` → `com.jn`, and so on), so a class that would violate the rule belongs in a different module.
- vis, jb and js do not import one another. A bot command belongs to the cost center of the data it works on: its steps are classes of that cost center, and its configuration (command, steps, names, texts) goes to the bot entities of jn (`JnEntityBotCommand*`) through `JnBotConfigurationSeeds`, returned by `getFirstRecordsToInsert` of one of its entities. The bot engine (jb) finds the commands of a bot by `botName` and runs each step by its class name, as `CcpMensageriaReceiver` runs a topic.
- Java target version is **17** across all modules. JDK 17 must be registered in Eclipse (Window → Preferences → Java → Installed JREs) and selected as the project's JRE System Library.
- JUnit 4 (not 5) is used throughout.
- Two modules use `spring-boot-starter-parent` as their own parent (`ccp_rest-api-handler-exception_spring` and `jn_mensageria-consumer_gcp-pubsub-push-spring_dependency`) — they are included in the aggregator but do not inherit from the root POM.
- `instanceof` pattern matching against a variable already declared as the same type (e.g., `CcpBusiness x instanceof CcpBusiness y`) is rejected by the compiler — replace with a `!= null` check.

## Architectural Rules

Named rules that govern how classes are written and how requests are interpreted. They can be cited by name or acronym ("apply MIAEL", "this violates OQL"). They apply to new code and to the interpretation of requirements; existing code is checked against them only when explicitly asked. Test code (`ccp_rest-api-tests_jobsnow`) follows them as well; its only exemption is the cost-center import rule in Key Conventions.

### Data entities

- **Automatic Entity Id (AEI)** — every entity's id is calculated from the fields annotated with `@CcpEntityFieldPrimaryKey`.
- **Entity Decorators (ED)** — any change of an entity's behavior on create, read, update, transfer, copy or delete is a decorator catalogued in `CcpEntityDecoratorTypes` (ccp), activated by an annotation of its own and positioned in the chain by the catalog. Every entity decorator lives in the ccp cost center; there are no decorators in jn, vis, jb or js. What a decorator needs from another cost center (an entity, an implementation class, a collaborator) is passed as a parameter of its annotation, as `@CcpEntityTwin` does with its bulk executor. No annotation is nested in another one, and an annotation with a single parameter names it `value`.
- **Side Effect Annotation (SEA)** — a business or a message run before or after a write or a transfer is an annotation whose name reads as a sentence: `@Ccp[Before|After][Save|Insert|Update|Delete|DeleteAnyWhere]From[Main|Twin]Entity(execute = {...}, operationHandlers = {...})`, `@Ccp[Before|After][TransferData|CopyData]From[Main|Twin]Entity(targetEntity = ..., execute = {...}, transferHandlers = {...})` (repeatable, one per target), `@Ccp<write>SendAn[Email|Instant]Message...AndIfFails[ThrowAnError|SaveAWarning|LogTheError](<message classes>)` and `@Ccp<transfer>SendAn...(messageTemplate = ..., targetEntity = ...)` (repeatable). The message classes implement `CcpEntityMessageTemplate` (in the platform, `JnMessageTemplate`).
- **Disposable Entity (DSE)** — records discarded after some time: `@CcpEntityDisposable(value = JnDisposableEntity.class, timeOption = <CcpEntityExpurgableOptions>)`.
- **Versionable Entity (VE)** — versioned records: `@CcpEntityVersionable(JnVersionableEntity.class)`, always together with the purge of the history: `@CcpEntityVersionablePurge(JnVersionablePurgeEntity.class)`.
- **Twin Entity (TWE)** — records with a mirror table that receives what is deleted from the main one: `@CcpEntityTwin(twinEntityName = <twin table>, bulkExecutorClass = JnExecuteBulkOperation.class, functionToDeleteKeysInTheCacheClass = JnDeleteKeysFromCache.class)`.
- **Read Only Entity (ROE)** — read-only records: `@CcpEntityOlyReadable` (spelled that way); they change only through bulk operations.
- **Cache Entity (CE)** — cacheable records: `@CcpEntityCache(<ttl in seconds>)`.
- **Async Entity (AE)** — records whose writes run asynchronously: `@CcpEntityAsyncWriter(JnAsyncWriterEntity.class)`.
- **Grouped Entity (GE)** — records kept in the groups of their parents: `@CcpEntityGrouperChild(value = {<parent entity>, ...}, beforeDecoratorClass = JnGrouperChildEntityBeforeWrite.class, afterDecoratorClass = JnGrouperChildEntityAfterWrite.class)`. Each parent entity is declared exactly once, in one of two ways: **oneToMany** (the parents come from the record's own values, e.g. a view has one recruiter and one resume) with `@CcpEntityGrouperParentCombinations(parent = <parent entity>, value = <combinations producer>)` on the entity, no field needed; **manyToMany** (the parents change with the record's contents, e.g. a resume in the group of each search it satisfies) with a list field of parent ids annotated with `@CcpStoredParentIdsField(value = <combinations producer>, parent = <parent entity>)`. If a stored-ids field is not asked for, the relationship is oneToMany. Records counted by key in the groups of their parents (one JSON of counters as the only child) use `@CcpEntityGrouperChildCounter(value = {<parent entity>, ...}, counterKeyClass = <key producer>, beforeDecoratorClass = JnGrouperChildCounterEntityBeforeWrite.class)`, each record counted once per parent.
- **LGPD Fields Entity (LFE)** — records holding sensitive data (e-mail, password): `@CcpEntityFieldsTransformer(<transformer catalog>)` on the entity, or `@CcpEntityFieldTransformer(<subclass of CcpJsonTransformersDefaultEntityField>)` on the field.

### Reading and writing data

- **Online Query Less (OQL)** — online requests (usually entering through an MVC controller) never run complex queries. Complex queries run only in a scheduled process, a queue listener or an asynchronous process: data that needs several entities and a complex query is produced there by a CQD, stored under an id, and the requester reads it by that id, directly or indirectly. Support bot commands are not online requests: only the support team (a few users) issues them, so they may run complex queries.
- **Complex Query Dsl (CQD)** — complex queries use the fluent interface of `CcpQueryOptions`.
- **Multi Get Id Entity (MGIE)** — fetching from several entities with no complex query, only id formation, uses `CcpCrud.unionAll`.
- **Flow Batch Operation Entity (FBOE)** — batches whose target entity is chosen dynamically are written by `JnExecuteBulkOperation.executeSelectUnionAllThenExecuteBulkOperation`.
- **Flow Status Entity Dsl (FSED)** — when throwing a `CcpErrorFlowDisturb` or running a `CcpBusiness` depends on which entity the record is (or is not) in, use `CcpGetEntityId` and its chained fluent interface. A flow goes to the database once for its presence checks: `CcpEntity.exists` is allowed only when it is the flow's sole presence check; two or more of them are rewritten as this fluent interface, and an `exists` next to the fluent interface becomes one more step of it (e.g. a daily limit checked inside the action is an `ifThisIdIsPresentInEntity` of the chain). An `exists` followed by `getOneById` of the same record is a single read: `ifThisIdIsPresentInEntity(...).executeAction(...)` (the action finds the record under `_entities`), `loadThisIdFromEntity` when the record is optional, or a pair of present/not present steps when both branches act; the same check repeated over several keys of one entity (a loop) is one read too: the loop only builds the array of keys passed to the `CcpGetEntityId` constructor, and `forEachIdPresentInEntity(...).executeAction(...)` runs the action once per key found, over that key with its own record under `_entities` (`ifThisIdIsPresentInEntity` holds when any key is present and hands over only the first record). A check that depends on a value read from another record cannot be a step and stays outside the chain.

### Code shape

- **Separated Business Type (SBT)** — every action is a class or enum item that implements `CcpBusiness`, directly or indirectly.
- **Dto Less (DL)** — no classes representing data (VO, DTO, Bean, Record, Model or similar); use `CcpJsonRepresentation`, which wraps a map and is parsed to and from JSON through `CcpJsonHandler`.
- **Dto Less Validation (DLV)** — validation happens in `CcpBusiness.execute`, which calls `CcpJsonValidatorEngine.validateJson`.
- **Immutable Object (IMO)** — classes that hold data are immutable.
- **Null Less (NL)** — passing `null` to a constructor or method, or returning `null` from a method, is forbidden; woven aspects enforce it by throwing `CcpNullParameterException` / `CcpNullReturnException`. The only allowed exceptions are members annotated with `@CcpAllowNullParameter` or `@CcpAllowNullReturn` (`com.ccp.aop`). Nulls coming from third-party libraries are handled defensively where needed.
- **Mitigate If And Else Less (MIAEL)** — `else` and `switch` (statement or expression) are forbidden; a decision over an enum goes to an abstract method of the enum (Enum as Decisor), any other one to `if`s that end in `return`/`throw`. Each `if` ends in `return` or `throw` (inside a loop, also `continue` or `break`). The `if` body is kept as small as possible, ideally one line; when it would be larger than the code after it, invert the condition so the short path goes inside the `if`. A simple ternary (`condition ? a : b`) is tolerated; a compound one (nested ternaries or one branch holding another ternary) is forbidden.
- **Enum as Decisor (EAD)** — when a decision depends on an enum, the enum declares an abstract method for it and each item implements it, whenever possible.
- **Decorator Everywhere (DEW)** — APIs for files, input streams, collections, e-mail, JSON, folders, hashes, numbers, passwords, properties files, reflection, strings, text, time, URLs or anything else demanding many operations sit behind a decorator in package `com.ccp.decorators`.
- **Extracted Expressions (EE)** — nested expressions are extracted into local variables before use, in method arguments, `if` conditions, loops and `return`s: instead of `takesString(human.getEye(Sides.LEFT).getColor().toString());` write `Eye eye = human.getEye(Sides.LEFT); Color color = eye.getColor(); String colorText = color.toString(); takesString(colorText);`. Safety exceptions that stay inline (each one breaks the code when extracted): calls to generic methods whose type comes from the target, `new X<>()` with diamond, the right side of `&&`/`||`, ternary branches and loop headers that are re-evaluated on every turn. Fluent interface chains (`CcpQueryOptions`, `CcpGetEntityId` and the like) are not split into variables either: breaking them hurts readability instead of helping it.
- **Multiline Lambda to Class (MLC)** — a lambda whose body spans more than one line becomes a class of its own, in its own file, implementing the functional interface the lambda implemented (`Function`, `Consumer`, `Predicate`, `Comparator`, `CcpBusiness`, `InvocationHandler` and the like). Every value the lambda captured becomes a constructor parameter kept in a `private final` field. A class whose only constructor takes no parameters makes it `private` and exposes `public final static <Class> INSTANCE`. One-line lambdas stay as they are. The new class is woven by the null aspects (NL), which the lambda was not: when the caller may pass `null` (a `java.lang.reflect.Proxy` calls `invoke` with `args = null` for methods without parameters), annotate the method with `@CcpAllowNullParameter` and/or `@CcpAllowNullReturn`.
- **Literal Less (LL)** — string literals are replaced by an item of an enum nested in the same file that implements `CcpJsonFieldName`. When the text cannot be an identifier, the item overrides `getValue`: `"S/A"` becomes `enum Fields implements CcpJsonFieldName { S_A { public String getValue() { return "S/A"; } } }`. Before creating an item, check whether it already exists in a centralizer enum the module can reach (`CcpJsonCommonsFields`; for jn, jb, vis and js also `JnJsonCommonsFields` and `JnJsonInstantMessengerFields`; for vis also `VisJsonCommonsFields`; any centralizer created later counts too) and use that one instead. Annotation attributes (`@SuppressWarnings`, OpenAPI texts, `@RequestMapping` paths and the like) keep their literals: they require compile-time constants, which `getValue()` is not.
- **One Type per File (OTF)** — every type gets its own file. Only two kinds stay nested: exceptions used solely inside the declaring file, and enums implementing `CcpJsonFieldName` whose only logic is `getValue` overrides (no other fields or methods).
- **Abstraction Technology Provider (ATP)** — a business module (`*_business_*`) depends only on `ccp_commons_jobsnow`, `aspectjtools` and other business modules.
