---
name: mapear-subtipos
description: Lista o fecho transitivo de subtipos de um tipo Java do workspace — filhos diretos e indiretos, em qualquer profundidade, com nível, tipo de declaração, módulo e arquivo. Use quando pedirem "quem implementa X", "quantos filhos de X existem", "quem estende X direta ou indiretamente", "todas as implementações de CcpBusiness / CcpService / CcpEntityConfigurator", ou ao avaliar o impacto de mexer numa interface base.
---

# Mapear subtipos de um tipo Java

Responde "quem herda deste tipo?" considerando **toda a cadeia**, não só a declaração direta.
Serve para dimensionar o raio de impacto de uma mudança numa interface base e para inventariar
famílias de tipos (services, entidades, transformers).

## Por que não é um grep

`grep "implements CcpBusiness"` acha **46** tipos. A resposta certa é **70**. Os 24 que faltam
herdam por caminho indireto:

- via interface intermediária — `VisServiceResume implements JnService`, e `JnService extends
  CcpService`, que por sua vez `extends CcpBusiness`;
- via classe-pai — `JnJsonTransformersFieldEntityTokenHash extends
  JnJsonTransformersFieldEntityFieldCalculateHash`, que implementa a interface.

Por isso a skill monta o grafo de herança do workspace inteiro e faz busca em largura a partir
do tipo raiz, em vez de casar texto.

## Argumento esperado

Nenhum obrigatório.

| Parâmetro | Padrão | Para quê |
|---|---|---|
| `-Root` | `C:\eclipse-workspaces\ccp` | raiz do workspace a varrer |
| `-Type` | `CcpBusiness` | nome **simples** do tipo raiz, sem pacote |
| `-IncludeTests` | desligado | inclui `ccp_rest-api-tests_jobsnow` |
| `-Csv` | nenhum | grava o resultado completo em CSV |

## Passos

1. Executar o script que acompanha a skill:

   ```powershell
   & "<raiz>\.claude\skills\mapear-subtipos\scripts\map-subtypes.ps1" -Type CcpBusiness
   ```

2. Apresentar ao usuário, nesta ordem:
   - **total**, e logo em seguida a quebra **por nível** (direto × indireto) — é a informação
     que justifica a skill existir;
   - **por tipo de declaração** (`class` / `interface` / `enum`);
   - **por módulo**;
   - a lista nominal, se o usuário pedir os nomes.

3. Ao dar o total, **separar interface de implementação**. As interfaces intermediárias são
   abstrações, não implementações: em `CcpBusiness` são 70 subtipos, mas só 63 implementam
   comportamento. Dizer só "70" esconde essa distinção.

4. Se o script emitir aviso de **colisão de nomes simples**, investigar antes de responder: o
   grafo é indexado por nome simples, então dois tipos homônimos em módulos diferentes seriam
   fundidos num nó só e o total ficaria errado.

## Como funciona

Varredura em uma única passada sobre os `.java`, fora de `target/`, `.git/`, `.metadata/`,
`node_modules/` e `bin/`.

Para cada arquivo, remove comentários de bloco, de linha e literais de string — senão a palavra
`class` dentro de um javadoc vira declaração fantasma. Depois casa cada declaração de tipo e
separa a cláusula `extends` / `implements`.

Dois cuidados no parser, ambos necessários:

- **Argumentos genéricos são removidos antes** de extrair os supertipos, do grupo mais interno
  para o mais externo. Sem isso, `implements Function<CcpJsonRepresentation, CcpJsonRepresentation>`
  entregaria `CcpJsonRepresentation` como se fosse supertipo.
- **`@interface` é descartado** por lookbehind. Declaração de anotação não pertence ao grafo de
  herança, e sem o descarte uma anotação homônima rouba o `kind` e o arquivo do tipo real — foi
  exatamente o que aconteceu com `JnEntityVersionable`, que existe como anotação **e** como
  classe no mesmo módulo.

Ao final o script confere, por conta própria, se algum nome do resultado é declarado em mais de
um arquivo, e avisa quando encontra.

## Restrições

- **É análise estática do fonte, não reflexão sobre bytecode.** Consequências:
  - classes anônimas (`new CcpBusiness() {...}`) e lambdas **não entram** — não têm nome. Para
    `CcpBusiness`, que é interface funcional, isso é relevante: hoje não existe nenhuma fora dos
    testes, mas se passar a existir, não aparecerá aqui;
  - tipos gerados por ITD do AspectJ (o projeto tece `CcpToStringAspect`) não aparecem.
  - Se precisar de precisão total, a alternativa é carregar os `target/classes` e usar
    `isAssignableFrom` — mas aí o resultado inclui anônimas e sintéticas, que costumam poluir
    a contagem.
- **O grafo é indexado por nome simples.** Duas classes homônimas em pacotes diferentes viram um
  nó só. O script avisa quando detecta; hoje não há colisão em `CcpBusiness` nem em
  `CcpEntityConfigurator`.
- **O projeto de testes fica fora por padrão.** Ligar `-IncludeTests` muda a base de comparação
  entre execuções.
- **Não usar `xargs` para alimentar um script de fecho transitivo.** Com 517 arquivos o `xargs`
  quebra em lotes e cada lote calcula um fecho **parcial** — o primeiro rascunho desta análise
  devolveu 4 em vez de 70 exatamente por isso. O script varre a árvore internamente.
- **Podar `.metadata/`** é obrigatório, não otimização: são ~300 MB de estado do Eclipse e a
  varredura não termina em tempo útil sem a poda.

## Baseline

Execução de 2026-09-17, `-Type CcpBusiness`, sem o projeto de testes (517 arquivos varridos):

| | |
|---|---|
| Total de subtipos | **70** |
| Diretos (nível 1) | 46 |
| Indiretos (nível 2) | 14 |
| Indiretos (nível 3) | 10 |
| Por declaração | 48 class · 15 enum · 7 interface |
| Por módulo | jn 27 · vis 24 · jb 8 · ccp_commons 7 · db-query 2 · db-crud 2 |

As 7 interfaces intermediárias: `CcpService`, `CcpTransformers`, `CcpHttpApiExecutor`,
`CcpJsonTransformersDefaultEntityField`, `JbBotBusiness`, `JnBusinessSendToMensageria` e
`JnService`. Esta última é a única de 2º nível e sozinha responde por 8 dos 10 de 3º nível —
os enums `JnService*` e `VisService*`, que são catálogos de endpoints, não regras de negócio.

Para conferência cruzada: `-Type CcpEntityConfigurator` dá **73**, todos diretos (jn 36 ·
vis 25 · jb 12) — é o inventário de entidades do sistema.
