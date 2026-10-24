---
name: ccp-atualizar-taxonomia-skills
description: Analisa a hierarquia de skills do ajustes_synonyms.txt, detecta incestos (ancestrais repetidos na cadeia), sincroniza o report_skills_modified.json com a taxonomia e acrescenta ao skills_synonyms_missing_descricoes.md as skills ainda sem descrição. Rodar depois de mudar linhas adicionarParent= do ajustes_synonyms.txt.
disable-model-invocation: true
---

# Atualizar Taxonomia de Skills

Analisa a hierarquia de skills definida em `ajustes_synonyms.txt`, detecta **incestos** (ancestrais repetidos na cadeia), sincroniza o `report_skills_modified.json` com o estado atual da taxonomia e atualiza o `skills_synonyms_missing_descricoes.md` com as skills que ainda não têm descrição registrada.

Use esta skill sempre que `ajustes_synonyms.txt` for modificado (adição, remoção ou alteração de linhas `adicionarParent=`).

## Argumento esperado

Nenhum argumento obrigatório. A skill opera sempre sobre os arquivos canônicos do projeto:

- **Taxonomia:** `ccp_rest-api-tests_jobsnow/documentation/jn/database/elasticsearch/ajustes_synonyms.txt`
- **JSON de saída:** `ccp_rest-api-tests_jobsnow/documentation/jn/database/elasticsearch/report_skills_modified.json`
- **MD de descrições:** `skills_synonyms_missing_descricoes.md`
- **Sinônimos:** `ccp_rest-api-tests_jobsnow/documentation/jn/database/elasticsearch/synonyms3.txt`

## Passos

1. **Ler e parsear `ajustes_synonyms.txt`**
   - Filtrar linhas `adicionarParent=SKILL,PAI1,PAI2,...`
   - Converter tudo para UPPER CASE e fazer trim
   - Construir `parent_map` (skill → lista de pais diretos) e `children_count` (skill → quantas skills a listam como pai)

2. **Calcular ancestrais completos para cada skill**
   - Recursão com detecção de ciclos via conjunto `visiting`
   - Para cada skill: lista completa de ancestrais (com duplicatas para detectar incesto) e lista deduplicada (preservando primeira ocorrência) para o campo `parent` do JSON

3. **Identificar incestos**
   - Uma skill é incesto (`hasRepeatedParent = true`) quando o mesmo ancestral aparece mais de uma vez na cadeia completa
   - Exemplos típicos: COLUNAROLAPNOSQLDATABASE (une COLUNAROLAP e NOSQLDATABASE que ambos derivam de DATABASE/NOSQL); RPG (AS400 e MAINFRAME ambos derivam de BACKEND)

4. **Carregar `report_skills_modified.json` existente**
   - Indexar por `skill` para preservar `description` e `synonym` de cada entry
   - Identificar skills presentes no JSON mas ausentes do `ajustes_synonyms.txt` (foram removidas da taxonomia)
   - Identificar skills no `ajustes_synonyms.txt` mas ausentes do JSON (foram adicionadas)

5. **Recomputar TODOS os campos derivados para cada skill**
   - `directParent`: pais diretos conforme `ajustes_synonyms.txt`
   - `parent`: lista deduplicada de todos os ancestrais
   - `hasRepeatedParent`: true se algum ancestral aparece mais de uma vez
   - `childrenCount`: quantas outras skills listam esta como pai direto
   - `hasNoParent`: true se não tem pais diretos (raiz da taxonomia)
   - `mirror` / `hasMirror`: skill com exatamente 1 pai cujo `childrenCount == 1`
   - `skillsWithCommonParents` / `hasSkillsWithCommonParentsSize`: outras skills que compartilham mais de 1 pai direto com esta
   - Preservar `description` do JSON existente; se skill nova, usar descrição fornecida ou string vazia
   - Preservar `synonym` do JSON existente; se skill nova, buscar em `synonyms3.txt`

6. **Atualizar `skills_synonyms_missing_descricoes.md`**
   - Parsear o MD para extrair todas as skills já descritas (regex `^\|\s*([A-Z0-9][A-Z0-9 .\-/#@_&\'+]*?)\s*\|` com MULTILINE)
   - Identificar skills do `ajustes_synonyms.txt` ausentes no MD
   - Anexar nova seção "## Categorias e Skills Adicionais" ao final do MD com as skills faltando e suas descrições do JSON

7. **Salvar `report_skills_modified.json`**
   - Ordenar entradas alfabeticamente por `skill`
   - Garantir encoding UTF-8
   - Reportar: total de entries, contagem de incestos, skills adicionadas, skills removidas

8. **Reportar resultado ao usuário**
   - Lista de incestos em formato de tabela com três colunas:
     - **Skill** — nome da skill com incesto
     - **Pais diretos** — cada pai direto seguido, entre parênteses, do array `parent` desse pai conforme o JSON salvo. Formato: `PAI1("anc1", "anc2", ...), PAI2("anc1", "anc3", ...)`
     - **Ancestral(is) repetido(s)** — os ancestrais que aparecem mais de uma vez na cadeia completa

   Exemplo de linha da tabela:
   ```
   ATLAS │ VETORIALDBCLOUD("VETORIALDB", "DATABASE", "CLOUD"), MONGODB("NOSQLDATABASE", "NOSQL", "DATABASE") │ DATABASE
   ```

   - Skills adicionadas ao JSON (novas na taxonomia)
   - Skills removidas do JSON (ausentes na taxonomia atual)
   - Skills adicionadas ao MD de descrições

## Como executar

Rodar o script que acompanha a skill (ele faz os passos 1 a 7 e imprime o material do passo 8):

```bash
python "C:/eclipse-workspaces/ccp/.claude/skills/ccp-atualizar-taxonomia-skills/scripts/atualizar_taxonomia.py"
```

Depois, montar a resposta ao usuário conforme o passo 8.

## Restrições

- Usar sempre `encoding="utf-8"` ao ler e escrever arquivos para preservar acentos e caracteres especiais.
- Nunca sobrescrever os campos `description` e `synonym` de uma entry já existente no JSON — apenas preservar.
- Skills novas que não têm descrição no JSON existente ficam com `description: ""` no JSON; o usuário deve preencher manualmente depois ou perguntar ao Claude as descrições.
- Se uma skill foi removida do `ajustes_synonyms.txt`, ela é removida do JSON. Confirmar com o usuário se a lista de removidas for grande (> 5 skills).
- O campo `parent` no JSON é a lista **deduplicada** de todos os ancestrais (não apenas os diretos). O campo `directParent` são apenas os pais imediatos.
- Incesto não é um erro da taxonomia necessariamente — é uma característica estrutural (diamante na hierarquia). Apenas reportar; não corrigir automaticamente.
