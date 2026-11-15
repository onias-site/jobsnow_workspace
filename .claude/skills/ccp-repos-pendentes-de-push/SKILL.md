---
name: ccp-repos-pendentes-de-push
description: Lista quais repositórios git do workspace (a raiz jobsnow_workspace e cada módulo) têm push pendente — commits locais que o GitHub ainda não tem —, com quantos commits faltam enviar e quantos arquivos ainda estão sem commit. Use quando pedirem "quais repositórios estão pendentes de push", "o que falta subir", "o que falta dar push", ou antes de rodar o fazPushEmTodosProjetosLocais.bat / fazPullEmTodosProjetosLocais.bat.
disable-model-invocation: true
---

# Repositórios pendentes de push

O workspace não é monorepo: a raiz e cada módulo são repositórios git separados. Esta skill varre todos e mostra os que
têm **commits locais ainda não enviados** ao remoto (mudou em 2026-11-14 a pedido do usuário; antes listava só as
alterações não commitadas).

## Passos

1. Rodar o script. Ele não faz `git fetch`: compara cada branch com a referência remota local (`@{u}`), que o último
   push, pull ou fetch atualizou. Por isso é rápido e responde exatamente "o que eu ainda não enviei" (um commit que
   outra máquina tenha mandado ao GitHub não aparece, e não importa para o push).

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-repos-pendentes-de-push/scripts/pendentes.sh"
   ```

   Saída, separada por TAB:
   - `repo <nome> <commits a enviar> <arquivos sem commit> <branch>`, um por repositório com push pendente;
   - `semUpstream <nome> <branch>`, branch sem remoto configurado (tudo nela é pendente);
   - `resumo <com push pendente> <sem upstream> <total de repositórios>`.

2. Apresentar em grade desenhada (bloco de código, como manda a skill ccp-exibir-em-tabela) só os repositórios com push
   pendente: **#** (a partir de 1) | **Repositório** | **Commits a enviar** | **Sem commit**. Fechar com a linha de
   totais (soma dos commits e dos arquivos). Sem coluna de último commit (retirada a pedido do usuário em 2026-11-14).
3. Destacar o repositório cuja branch é diferente de `main` e os que aparecerem como `semUpstream`.
4. Em uma linha, citar os repositórios que têm arquivos sem commit mas nenhum commit a enviar não aparecem aqui; se o
   usuário quiser vê-los, `git status` em cada um.
5. Lembrar que o push é do usuário (`fazPushEmTodosProjetosLocais.bat`) e que o `fazPullEmTodosProjetosLocais.bat` faz
   `reset --hard`: descartaria o que estiver sem commit e, sem push antes, poderia perder os commits locais.

## Restrições

- Somente leitura: nunca commitar, fazer push, pull ou fetch a partir desta skill.
- Se nada estiver pendente, responder em uma linha.
