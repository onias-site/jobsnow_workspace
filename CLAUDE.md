# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**jobsnow** is a multi-module Java backend framework paired with a legacy React frontend. The backend is built around a custom decorator/DI pattern framework with Elasticsearch as the primary database. All 27 modules live together under a single aggregator `pom.xml` at the root and are managed as one Eclipse workspace (`C:\eclipse-workspaces\ccp`), each module being a separate Eclipse project.

## Module Structure

The root `pom.xml` is an aggregator (not a parent — modules keep their own `<parent>` declarations). Build order is encoded in the module list.

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
| 1 | `ccp_text-extractor_apache-tika` | Text extraction via Tika |
| 1 | `jn_business_jobsnow` | Core jobsnow business logic |
| 1 | `ccp_rest-api-handler-exception_spring` | Spring Boot exception handler (has own Spring parent) |
| 2 | `ccp_db-query_elasticsearch` | Elasticsearch query builder |
| 2 | `vis_business_jobsnow` | Visualization business logic |
| 2 | `jb_business_jobsnow` | BackOffice business logic |
| 2 | `jn_mensageria-consumer_gcp-pubsub-push-spring_dependency` | PubSub push consumer / Spring Boot app (has own Spring parent) |
| 3 | `ccp_mocking_jobsnow` | Test mocks and DI wiring |
| 4 | `jb_instant-messenger-listener_jobsnow_dependency-chooser` | BackOffice bot listener |
| 5 | `jn_rest-api_spring_jobsnow_dependency-chooser` | jobsnow REST API / Spring Boot app |
| 5 | `vis_rest-api_spring_jobsnow_dependency-chooser` | Visualization REST API / Spring Boot app |
| 5 | `ccp_rest-api-tests_jobsnow` | Integration/API test suite |

## Repository Layout

This workspace is **not** a monorepo. Every module directory is its own git repository (28 of them, counting `jn_frontend_calistrato-react`, which is not a Maven module). Above them sits an umbrella repository for the workspace root itself:

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

**Entity System** — Annotation-driven:
- `@CcpEntityCache` — marks entities that use caching
- `@CcpEntityVersionable` — enables version history
- `@CcpEntityTwin` — twin-document pattern
- `@CcpEntityDataTransfer` — DTO mapping

**Database Layer** — `CcpCrud` interface backed by Elasticsearch:
- `CcpQuery` / `CcpQueryBool` / `CcpQueryAggregations` — fluent query builder
- `CcpBulkExecutor` — bulk CRUD with pluggable handlers
- Schema definitions live in `documentation/jb/database/elasticsearch/scripts/entities/`
- Local logs go to `c:/logs/`

### Testing

Tests extend template base classes (`JnTemplateDeTestes`, `VisTemplateDeTestes`, `BaseTest`) that:
1. Bootstrap DI with real implementations
2. Load Elasticsearch schema from documentation scripts
3. Provide HTTP testing utilities (port 8080 assumed for local API)
4. Log full request/response for debugging

Business test class names follow Portuguese BDD conventions (e.g., `AoEntrarNaTelaDoCadastroDeSenha`).

### Frontend

Legacy React + Redux stack (React 15–16, Webpack 2, Bootstrap 3). Deployed to Google App Engine. State managed via Redux + redux-thunk; routing via react-router 3. Chart.js, Highcharts, and D3 used for data visualization.

## Key Conventions

- Field names in JSON are defined as enums and passed to `CcpJsonRepresentation` accessors — avoid bare string keys.
- Cost centers follow a strict dependency order: **ccp → jn → vis/jb**. A `com.ccp` class must never import `com.jn`, `com.vis` or `com.jb`; a `com.jn` class must never import `com.vis` or `com.jb`. `ccp_rest-api-tests_jobsnow` is the only module exempt from the rule. Module prefix and root package always agree (`ccp_*` → `com.ccp`, `jn_*` → `com.jn`, and so on), so a class that would violate the rule belongs in a different module.
- Java target version is **17** across all modules. JDK 17 must be registered in Eclipse (Window → Preferences → Java → Installed JREs) and selected as the project's JRE System Library.
- JUnit 4 (not 5) is used throughout.
- Two modules use `spring-boot-starter-parent` as their own parent (`ccp_rest-api-handler-exception_spring` and `jn_mensageria-consumer_gcp-pubsub-push-spring_dependency`) — they are included in the aggregator but do not inherit from the root POM.
- `instanceof` pattern matching against a variable already declared as the same type (e.g., `CcpBusiness x instanceof CcpBusiness y`) is rejected by the compiler — replace with a `!= null` check.
