---
name: ccp-commit-e-push
description: Sugere a mensagem de commit do dia a partir do que mudou nos repositórios do workspace e já roda o fazPushEmTodosProjetosLocais.bat com ela (add, commit e push na raiz e em cada módulo), respondendo sozinho aos prompts do .bat. Use quando pedirem "sugira uma mensagem de commit", "mensagem para o fazPush", "faz o push de tudo", "commita e sobe tudo", "rode o fazPushEmTodosProjetosLocais".
---

# Mensagem de commit e push de todos os repositórios

O workspace não é monorepo: a raiz e cada módulo são repositórios git separados, e o
`fazPushEmTodosProjetosLocais.bat` faz `git add .`, `git commit -m "<mensagem>"` e `git push` em todos, com uma
mensagem só. Esta skill escreve essa mensagem e roda o `.bat`. Pedida pelo usuário em 2026-10-10, que fazia isso à mão
todo dia.

## Passos

1. **Ver o que está pendente** com o script da skill `ccp-repos-pendentes-de-push` (faz `git fetch`):

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-repos-pendentes-de-push/scripts/pendentes.sh"
   ```

   - Nada pendente: dizer isso em uma linha e parar.
   - Algum repositório **atrás** do remoto (BEHIND > 0) ou `sem-upstream`: **não rodar o push**. O `git push`
     daquele repositório seria rejeitado depois do commit. Avisar quais são e parar.

2. **Entender o que mudou**, para a mensagem dizer o assunto e não a lista de arquivos:
   - o que foi feito nesta conversa (a fonte principal, quando houver);
   - em cada repositório pendente, `git -C <repo> status --porcelain` e `git -C <repo> diff --stat HEAD`, e o
     `git diff` dos arquivos que não ficarem claros pelo nome;
   - o estilo das mensagens anteriores: `git -C C:/eclipse-workspaces/ccp log -8 --format=%s`.

3. **Escrever a mensagem** no estilo do histórico do usuário:
   - português, uma linha só, começando em minúscula, sem ponto final;
   - os assuntos principais separados por vírgula e "e", do mais importante para o menos;
   - até uns 200 caracteres; nomes de classe ou skill só quando forem o assunto;
   - exemplos do histórico: "correcao dos 23 bugs restantes da campanha de cobertura (fora do vis), regras de
     arquitetura no CLAUDE.md e remocao dos else (MIAEL)" · "correçoes de login e de skills e suas hierarquias";
   - **proibidos** (quebram o `.bat`): aspas duplas, `!`, `%`, `^`, `&`, `|`, `<`, `>`. O script recusa a mensagem
     se tiver algum. Acentos podem: passam inteiros.

4. **Mostrar a mensagem** ao usuário em uma linha e **rodar o push na mesma resposta**, sem perguntar: invocar a
   skill já é o pedido para subir. Rodar **em segundo plano**, porque o `.bat` percorre todas as subpastas
   (`for /d /r`) e leva alguns minutos:

   ```powershell
   & "C:\eclipse-workspaces\ccp\.claude\skills\ccp-commit-e-push\scripts\push-com-mensagem.ps1" -Message "<mensagem>"
   ```

   O script responde aos três prompts do `.bat` (o `pause` do começo, a mensagem e o `pause` do fim) e grava a
   saída em `%TEMP%\push-<data>.log` (a última linha mostra o caminho).

5. **Conferir** depois que terminar: rodar de novo o `pendentes.sh` e ler o log.
   - O esperado é nenhum repositório pendente, a não ser os que mudaram durante o push.
   - Relatar quantos repositórios foram commitados e enviados, e qualquer falha (push rejeitado, conflito,
     credencial) com o repositório e a linha do log.
   - Se um push falhou, o commit local ficou feito: o repositório aparece com "Commits à frente" no `pendentes.sh`.
     Não tentar consertar sozinho; mostrar ao usuário.

## Restrições

- Nunca usar `--force`, nunca fazer pull nem reset: o `fazPullEmTodosProjetosLocais.bat` faz `reset --hard` e não
  faz parte desta skill.
- Não editar o `.bat`. Ele continua servindo para uso manual, com a mensagem digitada.
- Se uma rodada do relatório de cobertura estiver em andamento (`coverage-report.ps1`), o push pode seguir. O
  histórico da cobertura (`.claude/skills/ccp-relatorio-de-cobertura/history`) que ela gravar depois entra no próximo
  push.
