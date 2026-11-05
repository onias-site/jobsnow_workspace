---
name: ccp-conceito-outras-interfaces
description: Conceito "Outras interfaces" da taxonomia de tipos de classes Java do JobsNow. Categoria de sobra - interfaces não cobertas pelas demais (CcpJsonValidator, CcpJsonFieldType, JnSystemMessage, CcpToString) e classes que as implementam, inclusive as lambdas extraídas pela regra MLC (Function, Consumer, Predicate, Comparator). Use ao classificar uma classe que implementa interface funcional ou auxiliar.
---

# Outras interfaces

## Definição

A categoria de sobra: interfaces que não pertencem a nenhuma outra categoria e as classes que implementam uma interface sem cair numa categoria de maior prioridade. Inclui as lambdas de várias linhas que viraram classe pela regra MLC (implementam `Function`, `Consumer`, `Predicate`, `Comparator`, `Callable`, `Runnable`), as combinações dos groupers e os validadores customizados.

## Exemplos

`CcpJsonValidator`, `CcpJsonFieldType`, `JnSystemMessage`, `CcpToString`, `VisResumeHashCombinations`, `JnGroupersAddChildItem`, `VisHistoryKeyCollector`, `VisSkillRankingComparator`, `VisJsonValidatorHomeOfficeAlone`

## Lugar na taxonomia

Cada tipo Java de produção conta para **uma única** categoria: a primeira, na ordem de prioridade, cujo critério ele atende. Esta é a prioridade 19 de 19. A tabela completa, as listas nominais e a contagem atual estão em `/ccp-listar-tipos-de-classes` (`.claude/skills/ccp-listar-tipos-de-classes`). Quantidade em 2026-11-04: **57** tipos (4,9% dos 1.167).

## Observações

- Coincidir com esta categoria nunca é conflito: ela só recebe o que nenhuma outra pegou.
- Classe nova de DSL, motor, web ou utilitário cai aqui até entrar na lista nominal do script.
