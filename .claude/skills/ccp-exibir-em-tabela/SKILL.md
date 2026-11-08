---
name: ccp-exibir-em-tabela
description: Toda listagem de dados apresentada ao usuário (contagens, registros, estatísticas, pendências, achados, comparações, resultados) sai como grade desenhada à mão com bordas ┌─┬─┐ │ ├─┼─┤ └─┴─┘ dentro de um bloco de código, nunca como fichas "#: 1 / Campo: valor / ────", nunca como lista com marcadores e nunca como tabela Markdown. Vale sempre, com ou sem pedido. Use também quando o usuário pedir "exiba em formato de tabela", "exiba em tabela", "mostre em tabela", "visualização em tabela", "põe numa tabela", "em forma de tabela", "tabulado", "quero ver em grade", "isso não é tabela", "virou ficha" ou qualquer variação com esse sentido.
---

# Exibir em tabela

**Regra permanente (2026-11-08):** o usuário nunca quer ver uma listagem de dados apresentada por mim em formato de
lista. Toda listagem sai na **grade com bordas**, já na primeira resposta, sem esperar o pedido. Isso vale também quando
outra skill manda "apresentar uma tabela Markdown": para o usuário, "tabela" é sempre esta grade.

O formato **proibido** é o de fichas, que o terminal gera quando uma tabela Markdown passa da largura (e também
qualquer lista com marcadores que enumere itens com atributos):

```
#: 1
Point: business is the least directly tested package (1.95 tests per class).
Why it matters: It holds the security rules, ...
────────────────────────────────────────
#: 2
...
```

O formato esperado é este (referência do usuário, 2026-11-08):

```
┌────────────────────────────┬─────────┬──────────┬──────┬────────┬──────┬───────────┬───────────┬───────────┐
│           Pacote           │ Classes │ Métodos  │ IMC  │ Testes │ ITC  │ % do tot. │ % do tot. │ % do tot. │
│                            │         │ públicos │      │        │      │ métodos   │ testes    │ classes   │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ com.ccp                    │     635 │    1.123 │ 1,77 │  1.887 │ 2,97 │    61,47% │    58,69% │    37,66% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ com.vis                    │     217 │      286 │ 1,32 │    376 │ 1,73 │    15,65% │    11,70% │    12,87% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ com.jn                     │     148 │      267 │ 1,80 │    498 │ 3,36 │    14,61% │    15,49% │     8,78% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ com.js                     │      97 │      102 │ 1,05 │    292 │ 3,01 │     5,58% │     9,08% │     5,75% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ com.jb                     │      37 │       49 │ 1,32 │    162 │ 4,38 │     2,68% │     5,04% │     2,19% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ ccp_rest-api-tests_jobsnow │     552 │        0 │ 0,00 │      0 │ 0,00 │     0,00% │     0,00% │    32,74% │
├────────────────────────────┼─────────┼──────────┼──────┼────────┼──────┼───────────┼───────────┼───────────┤
│ Total                      │   1.686 │    1.827 │ 1,08 │  3.215 │ 1,91 │      100% │      100% │      100% │
└────────────────────────────┴─────────┴──────────┴──────┴────────┴──────┴───────────┴───────────┴───────────┘
```

## Como montar

1. Pegue todos os itens e campos da listagem, sem perder nenhum.
2. Desenhe a grade **à mão, dentro de um bloco de código** (```), com os caracteres `┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ │ ─`. Não use
   tabela Markdown (`| --- |`): é ela que o terminal transforma em fichas quando fica larga.
3. Quando os itens não têm uma coluna que os identifique (achados, pendências, decisões), a primeira coluna é `#`, com
   contador incremental a partir de 1. Quando já existe uma coluna identificadora (pacote, repositório, e-mail), o `#`
   é opcional.
4. Cabeçalho centralizado; pode ocupar duas ou mais linhas para que a coluna não fique mais larga que os dados.
5. Números alinhados à direita, com separador de milhar e vírgula decimal (`1.123`, `1,77`, `61,47%`). Texto alinhado
   à esquerda.
6. Separe **todas** as linhas de dados com `├─┼─┤`. A linha de totais, quando houver, é a última.
7. Cada coluna tem largura fixa; texto longo é **quebrado em várias linhas dentro da mesma célula** (as outras células
   da linha ficam em branco nas linhas de continuação), nunca truncado.
8. Conte os caracteres: todas as linhas da grade têm exatamente a mesma largura e os `│` ficam alinhados. Acentos
   contam como um caractere. Para listagens grandes, gere a grade com um script (Python com `─` e afins, nunca o
   caractere literal no comando do Bash, que dá exit 127) em vez de desenhar à mão.
9. Texto corrido só antes ou depois da grade, curto.

## Largura máxima: dividir, nunca desformatar

A grade nunca pode passar da largura da janela do terminal, porque aí as linhas quebram e a tabela desmancha. A
referência do usuário tem cerca de 150 caracteres e aparece inteira; não passe disso.

Se as colunas não couberem, **divida em duas (ou mais) grades**, cada uma dentro da largura, repetindo em todas a coluna
que identifica a linha (`#` ou o nome do item), na mesma ordem de linhas. Exemplo: a 1ª grade com o item e as
contagens, a 2ª com o item e as porcentagens. Para textos longos, a 1ª grade traz as colunas curtas e a 2ª só `#` e o
texto. Nunca encolha a grade truncando dados nem volte ao formato de fichas.

## Exemplo com célula de várias linhas

```
┌─────┬──────────────────────────────┬──────────────────────────────────────────────┐
│  #  │            Ponto             │               Por que importa                │
├─────┼──────────────────────────────┼──────────────────────────────────────────────┤
│   1 │ business é o pacote menos    │ Guarda as regras de segurança, provavelmente │
│     │ testado diretamente (1,95    │ exercitadas só de forma indireta pelos       │
│     │ teste por classe)            │ testes do JsServiceLogin (88 em services).   │
├─────┼──────────────────────────────┼──────────────────────────────────────────────┤
│   2 │ 7 classes nunca citadas por  │ A maioria protege a sessão.                  │
│     │ nenhum teste                 │                                              │
└─────┴──────────────────────────────┴──────────────────────────────────────────────┘
```
