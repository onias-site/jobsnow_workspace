---
name: ccp-atualizar-tela-repositorios
description: Refaz a lista de repositórios GIT da tela "Nosso backend" do front end, depois que um repositório foi acrescentado, retirado, renomeado ou teve sua descrição alterada. Só roda quando o usuário digita /ccp-atualizar-tela-repositorios.
disable-model-invocation: true
---

# Atualizar a tela de repositórios

A tela "Nosso backend" (`BackendConcepts.tsx`) lista os repositórios GIT a partir de um único arquivo:
`jn_frontend_calistrato-react/presentation/pages/nosso-backend/repositoriesCatalog.ts`. Os títulos das seções, as
quantidades e os links saem dele, então a atualização da tela é a deste arquivo.

## Passos

1. Rodar o script, somente leitura:

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-atualizar-tela-repositorios/scripts/comparar.sh"
   ```

2. Aplicar em `repositorySections`, com Edit, o que a saída pedir:
   - `ADICIONAR`: incluir o repositório. Vale o nome do GitHub, que vem do script e pode diferir do nome da pasta.
     Prefixo `ccp_` vai em "Repositórios GIT do CCP"; os demais, em "Repositórios GIT das demais siglas". A descrição é o
     propósito do CLAUDE.md traduzido para o português, em uma frase terminada em ponto.
   - `RETIRAR`: apagar o repositório do catálogo.
   - Um `RETIRAR` e um `ADICIONAR` que sejam o mesmo módulo com outro nome são uma renomeação: trocar o nome e manter a
     descrição, ajustando-a se o propósito mudou.
   - `DESCRICAO`: comparar o **sentido** da descrição da tela com o propósito do CLAUDE.md e reescrever só a que divergir.
     Diferença de tradução ou de detalhe não é divergência: a tela resume.
   - `SEM_PROPOSITO`: não inventar a descrição. Se o módulo for novo, ler o `pom.xml` e o código para escrevê-la e
     incluí-lo também na tabela "Module Structure" do `CLAUDE.md`, que é a fonte das descrições.
3. Manter a ordem alfabética dentro de cada seção e o estilo das linhas do arquivo.
4. Rodar o script de novo: não pode sobrar `ADICIONAR` nem `RETIRAR`, e os dois números de `TOTAL` têm de ser iguais.
5. Se o arquivo mudou, conferir os tipos, filtrando pelos arquivos da tela (o projeto tem erros antigos em outros lugares):

   ```bash
   cd "C:/eclipse-workspaces/ccp/jn_frontend_calistrato-react" && npx tsc --noEmit | grep nosso-backend
   ```

6. Responder com uma tabela do que mudou: **Repositório** | **Mudança** | **Seção**, e o total de repositórios. Se nada
   mudou, responder em uma linha.

## Restrições

- Alterar só `repositoriesCatalog.ts` e, no caso de `SEM_PROPOSITO`, a tabela do `CLAUDE.md`.
- Não commitar nem fazer push.
- Não criar nem apagar repositório: a skill só espelha o que já existe no git.
