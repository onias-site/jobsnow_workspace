# Skill Creator

Cria uma nova skill (slash command) no projeto atual.

## Argumento esperado

$ARGUMENTS deve conter:
- **nome** da skill (kebab-case, ex: `criar-teste`)
- **descrição** do que a skill faz (em linguagem natural)

Exemplo de invocação:
```
/skill-creator criar-teste | Gera classe de teste JUnit 4 para uma business class
```

## O que fazer

1. Extraia o nome da skill e a descrição a partir de `$ARGUMENTS`.
   - Se o separador `|` estiver presente, tudo antes é o nome e tudo depois é a descrição.
   - Se não houver separador, use `$ARGUMENTS` como nome e peça uma descrição ao usuário antes de continuar.

2. Determine o caminho de destino:
   - Projeto: `.claude/commands/<nome>.md`
   - Se o diretório `.claude/commands/` não existir, crie-o.

3. Pergunte ao usuário (se não estiver claro no argumento):
   - Quais são os **passos** que a skill deve executar?
   - A skill recebe **argumentos**? Se sim, o que cada um representa?
   - Há **restrições** ou **convenções** que a skill deve seguir?

4. Gere o arquivo `.claude/commands/<nome>.md` seguindo esta estrutura:

```markdown
# <Título legível da skill>

<Descrição do que a skill faz e quando usá-la.>

## Argumento esperado

$ARGUMENTS representa: <o que o usuário passa>

## Passos

1. <Passo 1>
2. <Passo 2>
3. <Passo N>

## Restrições

- <Restrição ou convenção relevante>
```

5. Confirme ao usuário o caminho do arquivo criado e mostre o conteúdo gerado.
6. Sugira como testar: `/nome-da-skill <argumento de exemplo>`

## Restrições

- Use sempre kebab-case para o nome do arquivo.
- Não crie a skill em `~/.claude/commands/` (global) a menos que o usuário peça explicitamente.
- Não inclua lógica de negócio complexa diretamente na skill — ela deve orquestrar passos, não substituir o julgamento do Claude.
- Se a skill criada for muito similar a uma já existente em `.claude/commands/`, avise o usuário e sugira atualizar a existente em vez de duplicar.
