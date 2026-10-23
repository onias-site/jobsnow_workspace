# Listar Conceitos

Apresenta os conceitos do sistema (as regras de arquitetura nomeadas e os centros de custo) em tabela, com a sigla e o
acrônimo (nome por extenso) de cada um.

## Argumento esperado

Nenhum. Se vier um texto (ex.: `entidade`, `OQL`), mostrar só as linhas cuja sigla, acrônimo ou seção contenham esse
texto, sem diferenciar maiúsculas.

## Passos

1. **Ler a seção `## Architectural Rules` do `CLAUDE.md` da raiz do workspace** (`C:\eclipse-workspaces\ccp\CLAUDE.md`).
   A fonte é sempre o arquivo, nunca uma lista decorada: regras e siglas podem ter mudado.
   - Cada regra é uma linha no formato `- **<Acrônimo> (<SIGLA>)** — <descrição>`.
   - A seção da regra é o `###` acima dela (`Data entities`, `Reading and writing data`, `Code shape`).
   - Regra sem sigla entre parênteses: mostrar `—` na coluna Sigla e avisar abaixo da tabela.

2. **Montar a tabela das regras**, em ordem alfabética de sigla (regra sem sigla vai para o fim, em ordem alfabética
   de acrônimo):

   | # | Sigla | Acrônimo | Seção |
   |---|---|---|---|

   - `#` incremental a partir de 1.
   - Seção traduzida: `Data entities` → Entidades; `Reading and writing data` → Leitura e escrita de dados;
     `Code shape` → Forma do código. Seção nova: traduzir no mesmo estilo.

3. **Montar a tabela dos centros de custo**, com as mesmas colunas `#`, `Sigla` e `Acrônimo`, também em ordem
   alfabética de sigla:

   | # | Sigla | Acrônimo |
   |---|---|---|
   | 1 | CCP | não registrado: é o framework (DI, decorators, interfaces de tecnologia) |
   | 2 | JB | BackOffice: suporte e dados estáticos |
   | 3 | JN | JobsNow: a infraestrutura central, com entidades e utilitários compartilhados |
   | 4 | JS | JobsNow System: o serviço de login e suas entidades |
   | 5 | VIS | Visualização: cobrança por visualização de currículo |

   Se o `CLAUDE.md` passar a citar outro centro de custo na regra de dependência (`ccp → jn → vis/jb/js`), acrescentar
   a linha na posição alfabética.

4. **Fechar** com uma linha com o total de regras e quantas estão em cada seção. Se alguma sigla aparecer repetida,
   apontar a colisão.

## Restrições

- Somente leitura: não alterar o `CLAUDE.md` nem outro arquivo.
- Sigla nova se propõe em conversa e se registra no `CLAUDE.md`; este comando só apresenta o que está lá.
