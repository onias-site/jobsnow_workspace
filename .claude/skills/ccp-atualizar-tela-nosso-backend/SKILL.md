---
name: ccp-atualizar-tela-nosso-backend
description: Atualiza a tela "Nosso backend" do front end (conceitos, repositórios GIT e Swagger) depois que o CLAUDE.md, um repositório ou o Swagger mudou. Só roda quando o usuário digita /ccp-atualizar-tela-nosso-backend.
disable-model-invocation: true
---

# Atualizar a tela Nosso backend

Funde as antigas `ccp-atualizar-tela-repositorios`, `ccp-atualizar-tela-swagger` e o comando `ccp-listar-conceitos`
(fusão pedida pelo usuário em 2026-11-01).

A tela (`BackendConcepts.tsx`) sai de três arquivos de `jn_frontend_calistrato-react/presentation/pages/nosso-backend/`.
Os títulos, as quantidades, as tabelas e os links saem deles, então atualizar a tela é atualizar estes arquivos:

| Porção da tela | Arquivo | Fonte |
|----------------|---------|-------|
| Conceitos (Entidades, Leitura e escrita de dados, Forma do código, Centros de custo) | `conceptsCatalog.ts` | `## Architectural Rules` e regra de dependência do `CLAUDE.md` |
| Repositórios GIT | `repositoriesCatalog.ts` | Repositórios git do workspace e tabela `Module Structure` do `CLAUDE.md` |
| Swagger do JS e do VIS (interface de testes do Swagger, por `swagger-ui-react`) | `swaggerCatalog.ts` (gerado, com o documento OpenAPI inteiro) | `/api-docs` das APIs locais |

Fazer sempre as três partes. Uma parte que não puder ser feita (API fora do ar) não impede as outras: fica registrada no
relatório final.

## 1. Conceitos

1. Rodar o script, somente leitura:

   ```bash
   python "C:/eclipse-workspaces/ccp/.claude/skills/ccp-atualizar-tela-nosso-backend/scripts/comparar-conceitos.py"
   ```

2. Aplicar em `conceptSections`, com Edit, o que a saída pedir:
   - `ADICIONAR`: incluir a regra na seção indicada, em ordem alfabética de sigla. A explicação é a regra do `CLAUDE.md`
     resumida em uma frase em português, terminada em ponto, para quem não lê código.
   - `RETIRAR`: apagar o conceito.
   - Um `RETIRAR` e um `ADICIONAR` que sejam a mesma regra com outra sigla são uma renomeação: trocar a sigla e o acrônimo
     e manter a explicação, ajustando-a se o sentido mudou.
   - `MOVER`: levar o conceito para a seção indicada. `ACRONIMO`: trocar o nome.
   - `DESCRICAO`: comparar o **sentido** da explicação da tela com a regra do `CLAUDE.md` e reescrever só a que divergir.
     Diferença de tradução ou de detalhe não é divergência: a tela resume.
   - `SEM_SIGLA`, `SIGLA_REPETIDA`: não mexer no `CLAUDE.md`; apontar no relatório final.
   - `SECAO_NOVA`: criar a seção em `conceptSections`, antes de "Centros de custo", e incluir a tradução em `SECTIONS`, no
     script.
   - `CENTRO_ADICIONAR`: incluir o centro de custo, com a explicação tirada das regras e dos módulos dele no `CLAUDE.md`.
     `CENTRO_RETIRAR`: apagar.
3. Rodar o script de novo: não pode sobrar `ADICIONAR`, `RETIRAR`, `MOVER`, `ACRONIMO` nem `CENTRO_*`, e os números de
   `TOTAL` têm de bater dois a dois.

## 2. Repositórios

1. Rodar o script, somente leitura:

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-atualizar-tela-nosso-backend/scripts/comparar-repositorios.sh"
   ```

2. Aplicar em `repositorySections`, com Edit, o que a saída pedir:
   - `ADICIONAR`: incluir o repositório. Vale o nome do GitHub, que vem do script e pode diferir do nome da pasta.
     Prefixo `ccp_` vai em "Repositórios GIT do CCP"; os demais, em "Repositórios GIT das demais siglas". A descrição é o
     propósito do `CLAUDE.md` traduzido para o português, em uma frase terminada em ponto.
   - `RETIRAR`: apagar o repositório do catálogo.
   - Um `RETIRAR` e um `ADICIONAR` que sejam o mesmo módulo com outro nome são uma renomeação: trocar o nome e manter a
     descrição, ajustando-a se o propósito mudou.
   - `DESCRICAO`: comparar o **sentido**, como nos conceitos.
   - `SEM_PROPOSITO`: não inventar a descrição. Se o módulo for novo, ler o `pom.xml` e o código para escrevê-la e
     incluí-lo também na tabela "Module Structure" do `CLAUDE.md`, que é a fonte das descrições.
3. Manter a ordem alfabética dentro de cada seção e o estilo das linhas do arquivo.
4. Rodar o script de novo: não pode sobrar `ADICIONAR` nem `RETIRAR`, e os dois números de `TOTAL` têm de ser iguais.

## 3. Swagger

1. As APIs js (8082) e vis (8081) precisam estar no ar **com o código atual**. O `/api-docs` mostra o que a API carregou
   ao subir: se a mudança no Swagger veio depois disso, reinicie a API antes (e `mvn -o install -DskipTests` nos módulos
   alterados), senão o catálogo sai com o Swagger antigo sem nenhum aviso. Não use `ccp-subir-apis-e-recriar-entidades`
   só para isso: ela recria índices. Sem como saber se a API está atualizada, dizer isso no relatório final.

2. Rodar o script, que regrava o catálogo:

   ```bash
   python "C:/eclipse-workspaces/ccp/.claude/skills/ccp-atualizar-tela-nosso-backend/scripts/gerar-swagger.py"
   ```

   A saída tem uma linha por dado, separada por TAB:
   - `ADICIONADO`, `RETIRADO`, `ALTERADO`: seção, método e endereço do que mudou desde o catálogo anterior;
   - `SEM_RESUMO`: endpoint sem `summary` no Swagger;
   - `TOTAL`: seção e quantidade de endpoints;
   - `API_FORA_DO_AR`: a API não respondeu e nada foi gravado: registrar no relatório final.

## 4. Conferir e relatar

1. Se algum arquivo mudou, conferir os tipos, filtrando pelos arquivos da tela (o projeto tem erros antigos em outros
   lugares):

   ```bash
   cd "C:/eclipse-workspaces/ccp/jn_frontend_calistrato-react" && npx tsc --noEmit | grep nosso-backend
   ```

2. Responder com uma tabela do que mudou: **Porção da tela** | **Item** | **Mudança**, e os totais de conceitos,
   repositórios e endpoints. Citar os `SEM_RESUMO`, que se corrigem no controller da API, não aqui. Se nada mudou, responder
   em uma linha.

## Restrições

- Alterar só os três catálogos, `SECTIONS` do script e, no caso de `SEM_PROPOSITO`, a tabela do `CLAUDE.md`.
- Nunca editar `swaggerCatalog.ts` à mão: a próxima execução apaga a edição. Texto errado se corrige na interface
  OpenAPI da API (`*OpenApi*.java`), e os textos ficam em inglês, como no Swagger. API nova: incluir em `APIS`, no
  `gerar-swagger.py`.
- Regra ou sigla nova se propõe em conversa e se registra no `CLAUDE.md`; a tela só repete o que está lá.
- Não criar nem apagar repositório: a skill só espelha o que já existe no git.
- Não commitar nem fazer push.
