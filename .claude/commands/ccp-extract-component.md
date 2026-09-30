# Extract React Component

Extrai um trecho de linhas de um arquivo React TSX e cria um novo componente independente na mesma pasta, atualizando o arquivo original.

## Argumento esperado

`<caminho-do-arquivo> <linha-inicial> <linha-final> <NomeDoComponente>`

Exemplo: `jn_frontend_calistrato-react/presentation/auth/ModalLogin.tsx 272 279 UnlockTokenLink`

## Passos

1. **Validar arquivo**: Verificar se o arquivo informado existe. Se não existir, interromper com a mensagem:
   > "Arquivo não existe"

2. **Validar linhas**: Contar o total de linhas do arquivo e verificar se a linha inicial e a linha final estão dentro do intervalo válido. Se não estiverem, interromper com a mensagem:
   > "Linha inicial ou linha final não existem nesse arquivo"

3. **Ler o escopo**: Ler exatamente as linhas do intervalo informado (linha inicial até linha final, inclusive).

4. **Validar JSX balanceado**: Analisar o trecho extraído e verificar se todas as tags JSX de abertura possuem sua tag de fechamento correspondente dentro do escopo selecionado (tags auto-fechadas como `<Icon />` são válidas). Se o JSX estiver desbalanceado, interromper com a mensagem:
   > "Não é possível criar o componente, pois tags de fechamento não foram selecionadas, selecione corretamente as tags de início e encerramento para que possamos criar um novo componente"

5. **Analisar dependências**: Identificar todas as variáveis e identificadores usados no trecho extraído que são declarados fora desse trecho no arquivo original. Classificar cada um como:
   - **Desacoplável via store**: variáveis obtidas de um store global (zustand `create(...)`, Redux, Context API) — o novo componente pode importar e chamar o store diretamente, sem precisar de props.
   - **Import externo**: símbolos que vêm de `import` statements do arquivo original (componentes, funções utilitárias, ícones, libs) — serão reexportados no novo arquivo.
   - **Dependência local não desacoplável**: variáveis de estado local (`useState`, `useReducer`), variáveis computadas dentro do componente pai fora do escopo selecionado, parâmetros de função, etc. — estas **não podem** ser desacopladas sem props.

   Se existirem dependências locais não desacoplávies, interromper com a mensagem:
   > "Variável(is) contida(s) nesse escopo é(são) uma dependência do arquivo que estamos tentando componentizar"
   
   Listar quais variáveis causaram o bloqueio para que o usuário saiba o que ajustar.

6. **Criar o novo arquivo `.tsx`** na mesma pasta do arquivo de origem, com o nome `<NomeDoComponente>.tsx`. Estrutura do arquivo:
   - `'use client';` no topo
   - Imports necessários: `React` (se usar JSX), stores globais utilizados no trecho, imports externos do arquivo original que sejam referenciados no trecho
   - Declaração e exportação do componente: `export const <NomeDoComponente>: React.FC = () => { ... }`
   - Dentro do componente: destructuring do store (se necessário) e o JSX extraído
   - Nenhuma prop — tudo que for necessário deve ser obtido do store

7. **Atualizar o arquivo original**:
   - Adicionar o import do novo componente logo após os imports existentes: `import { <NomeDoComponente> } from '@/.../<NomeDoComponente>';` (usar o mesmo padrão de alias `@/` dos outros imports do arquivo)
   - Substituir as linhas extraídas (linha inicial até linha final) por `<NomeDoComponente />` com a indentação adequada
   - Verificar se algum `import` do arquivo original ficou sem uso após a extração; se sim, removê-lo

## Restrições

- O novo componente nunca recebe props — se precisar de dados, busca diretamente do store.
- Usar o mesmo padrão de alias de importação (`@/`) que o restante do arquivo original.
- Não criar arquivo se qualquer validação falhar — erros são terminais.
- Preservar a indentação original do JSX extraído dentro do novo componente.
- O nome do componente deve ser PascalCase; o nome do arquivo gerado é igual ao nome do componente (`NomeDoComponente.tsx`).
