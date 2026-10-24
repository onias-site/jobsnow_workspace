---
name: ccp-exibir-em-tabela
description: Reapresenta (ou apresenta) uma listagem de dados como grade desenhada à mão com bordas ┌─┬─┐ │ ├─┼─┤ └─┴─┘ dentro de um bloco de código, nunca como fichas "#: 1 / Campo: valor / ────". Use sempre que o usuário pedir "exiba em formato de tabela", "exiba em tabela", "mostre em tabela", "visualização em tabela", "põe numa tabela", "em forma de tabela", "tabulado", "quero ver em grade", "isso não é tabela", "virou ficha" ou qualquer variação com esse sentido.
---

# Exibir em tabela

Quando o usuário pede a listagem em tabela, ele quer **a grade com bordas**, e não o formato de fichas que o terminal
gera quando uma tabela Markdown passa da largura:

```
#: 1
Point: business is the least directly tested package (1.95 tests per class).
Why it matters: It holds the security rules, ...
────────────────────────────────────────
#: 2
...
```

Esse formato é **proibido** como resposta a esse pedido. O formato esperado é este:

```
┌─────┬──────────────────────────────┬─────────┬────────┬───────┬───────────┐
│  #  │            Rodada            │ Rodados │ Falhas │ Erros │ Ignorados │
├─────┼──────────────────────────────┼─────────┼────────┼───────┼───────────┤
│ 1   │ Anterior (antes do INSTANCE) │ 2811    │ 0      │ 1     │ 4         │
├─────┼──────────────────────────────┼─────────┼────────┼───────┼───────────┤
│ 2   │ Atual (depois do INSTANCE)   │ 2811    │ 0      │ 0     │ 4         │
└─────┴──────────────────────────────┴─────────┴────────┴───────┴───────────┘
```

## Como montar

1. Pegue os dados da última listagem apresentada (ou da que está sendo pedida) sem perder nenhum item nem campo.
2. Desenhe a grade **à mão, dentro de um bloco de código** (```), com os caracteres `┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ │ ─`. Não use
   tabela Markdown (`| --- |`): é ela que o terminal transforma em fichas quando fica larga.
3. A primeira coluna é sempre `#`, com contador incremental a partir de 1.
4. Largura total de no máximo ~120 caracteres. Cada coluna tem largura fixa; texto longo é **quebrado em várias linhas
   dentro da mesma célula** (as outras células da linha ficam em branco nas linhas de continuação), nunca truncado.
5. Separe as linhas de dados com `├─┼─┤` quando houver células de várias linhas, para que se saiba onde cada item
   termina.
6. Conte os caracteres: todas as linhas da grade têm exatamente a mesma largura e os `│` ficam alinhados. Acentos
   contam como um caractere.
7. Muitas colunas ou textos muito longos: divida em duas grades ligadas pelo `#` (uma de resumo com colunas curtas e
   outra com `#` e o texto longo), em vez de estourar a largura.
8. Texto corrido só antes ou depois da grade, curto.

## Exemplo com célula de várias linhas

```
┌─────┬──────────────────────────────┬──────────────────────────────────────────────┐
│  #  │ Ponto                        │ Por que importa                              │
├─────┼──────────────────────────────┼──────────────────────────────────────────────┤
│ 1   │ business é o pacote menos    │ Guarda as regras de segurança, provavelmente │
│     │ testado diretamente (1,95    │ exercitadas só de forma indireta pelos       │
│     │ teste por classe)            │ testes do JsServiceLogin (88 em services).   │
├─────┼──────────────────────────────┼──────────────────────────────────────────────┤
│ 2   │ 7 classes nunca citadas por  │ A maioria protege a sessão.                  │
│     │ nenhum teste                 │                                              │
└─────┴──────────────────────────────┴──────────────────────────────────────────────┘
```
