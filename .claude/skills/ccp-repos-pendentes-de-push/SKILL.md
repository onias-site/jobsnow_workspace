---
name: ccp-repos-pendentes-de-push
description: Lista quais repositórios git do workspace (a raiz jobsnow_workspace e cada módulo) têm algo a enviar — arquivos modificados, arquivos novos não rastreados ou commits à frente do remoto. Use quando pedirem "quais repositórios estão pendentes de push", "o que falta subir", "tem algo sem commit", "quais projetos mudaram", ou antes de rodar o fazPushEmTodosProjetosLocais.bat / fazPullEmTodosProjetosLocais.bat.
---

# Repositórios pendentes de push

O workspace não é monorepo: a raiz e cada módulo são repositórios git separados. Esta skill
varre todos e mostra só os que têm algo a enviar.

## Passos

1. Rodar o script (faz `git fetch` em cada repositório para o ahead/behind ficar correto):

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-repos-pendentes-de-push/scripts/pendentes.sh"
   ```

   Se o usuário pedir algo rápido/offline, passar `--sem-fetch` (o ahead passa a ser contra o
   último fetch conhecido).

2. Apresentar uma tabela Markdown só com os pendentes: **#** (contador
   iniciado em 1, incrementado a cada linha) | **Repositório** | **Modificados** |
   **Novos** | **Commits à frente** | **Atrás**. Fechar com a linha de totais.
3. Destacar:
   - repositório **atrás** do remoto (BEHIND > 0) — o push vai ser rejeitado até puxar;
   - `sem-upstream` — branch sem remoto configurado, o push do .bat falha nele;
   - branch diferente de `main`.
4. Se houver pendentes com alterações não commitadas, lembrar que o
   `fazPullEmTodosProjetosLocais.bat` faz `reset --hard` e descartaria esse trabalho.

## Restrições

- Somente leitura: nunca commitar, fazer push ou pull a partir desta skill.
- Se nada estiver pendente, responder em uma linha.
