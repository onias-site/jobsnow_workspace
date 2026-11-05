---
name: ccp-conceito-especificacao-e-implementacao
description: Conceito "Especificação / implementação" da taxonomia de tipos de classes Java do JobsNow. Interfaces de com.ccp.especifications (CcpBulkExecutor, CcpCrud, CcpCache, CcpEmailProvider, CcpHttpRequester...) e as classes que as implementam nos módulos de tecnologia. Use ao criar ou classificar uma especificação técnica ou sua implementação (regra ATP).
---

# Especificação / implementação

## Definição

As interfaces técnicas do pacote `com.ccp.especifications` (cache, banco, e-mail, arquivo, HTTP, mensageiro instantâneo, JSON, autenticação, mensageria, senha, texto) e as classes que as implementam nos módulos de tecnologia. Os módulos de negócio dependem só das especificações (regra ATP).

## Exemplos

`CcpBulkExecutor` / implementação no ElasticSearch, `CcpCache`, `CcpEmailProvider`, `CcpMensageriaSender`, `CcpHttpRequester`, `CcpQueryExecutor`, `CcpEntityDecoratorTypes`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 13 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **59** tipos (5,1% dos 1.167).

## Observações

- Perde para Entidades, Business e Infraestrutura para entidades, que também implementam interfaces de `com.ccp.especifications`.
- A implementação chega ao sistema por um Provedor de DI.
