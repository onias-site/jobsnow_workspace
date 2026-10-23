# Relatório das implementações de CcpBusiness

Lista todas as implementações de `CcpBusiness`, diretas ou indiretas, do workspace inteiro (o projeto de testes
incluído), com projeto, total de bytes e total de linhas de cada uma, marcando com `(acima da média)` o que passa da
média.

## Argumento esperado

Opcional. `$ARGUMENTS` pode trazer o nome **simples** de outro tipo raiz (ex.: `CcpEntityConfigurator`, `JnService`).
Vazio: `CcpBusiness`.

## Passos

1. Rodar o script, gravando o relatório completo na scratchpad da sessão (o nome do arquivo vem do tipo):

   ```bash
   python "C:/eclipse-workspaces/ccp/.claude/commands/scripts/relatorio_ccpbusiness.py" --tipo <tipo> --saida "<scratchpad>/relatorio_<tipo>.md"
   ```

   O script imprime o resumo (total, médias, quantos acima da média, quebra por tipo e por projeto) e grava o
   Markdown com a tabela inteira.

2. Ler o arquivo gravado e responder com:
   - na primeira frase, o total de implementações e as duas médias (bytes e linhas);
   - a quebra por tipo e por projeto, em uma linha cada;
   - as tabelas como o script grava, sem alterar: **uma tabela Markdown por projeto** (título com quantidade, bytes
     e linhas do projeto), colunas **#** | **Nome** | **Tipo** | **Bytes** | **Linhas**, ordenadas por bytes, com
     `(acima)` ao lado do valor acima da média geral, e o total geral no fim. Tabela única de 6 colunas com
     `(acima da média)` por extenso ficava larga demais e ilegível no terminal (reprovada pelo usuário em
     2026-10-22), assim como a versão desenhada à mão com caracteres de caixa;
   - o caminho completo do arquivo gravado.

## Como conta

- **Quem entra:** o fecho transitivo do tipo raiz pelo grafo de herança (`extends` e `implements`, por nome simples),
  como na skill `ccp-mapear-ccpbusiness`. Interfaces intermediárias (`CcpService`, `JnService`...) entram no grafo
  mas não viram linha: não são implementações.
- **Item de enum:** um enum do fecho vira uma linha **por item** (`JsServiceLogin.ExistsLoginEmail`), e o enum em si
  não aparece. O tamanho do item é o trecho dele, do nome até a vírgula ou o ponto e vírgula, com o corpo, se houver.
- **Lambda e classe anônima:** ficam de fora (não têm nome). No workspace não há lambda de mais de uma linha (regra MLC).
- **Tamanho de classe:** classe de topo = o arquivo inteiro (bytes no disco e linhas); classe aninhada = o trecho da
  própria declaração. O tipo mostra `classe`, `classe aninhada`, `classe abstrata` ou `item de enum`.
- **Média:** de todas as linhas da tabela; "acima da média" é estritamente maior.
- **Nome simples repetido** (classes de apoio de teste com o mesmo nome em pacotes diferentes): cada declaração só
  entra se ela própria estende ou implementa algo do fecho, e o pacote aparece entre parênteses na coluna Nome.
- Varre `.java` fora de `documentation/`, `target/`, `.metadata/`, `.git/`, `node_modules/`, `bin/`, `.claude/` e
  `.settings/`. Comentários e literais são mascarados antes de procurar declarações.

## Restrições

- Somente leitura: não compila, não roda testes e não altera arquivos do workspace (só grava o relatório na
  scratchpad).
- É análise estática do fonte: tipos gerados pelo AspectJ não aparecem.
