---
name: ccp-repos-pendentes-de-push
description: Lista quais repositórios git do workspace (a raiz jobsnow_workspace e cada módulo) têm alterações não commitadas — arquivos modificados, arquivos novos não rastreados ou arquivos removidos. Use quando pedirem "quais repositórios estão pendentes de push", "o que falta subir", "tem algo sem commit", "quais projetos mudaram", ou antes de rodar o fazPushEmTodosProjetosLocais.bat / fazPullEmTodosProjetosLocais.bat.
disable-model-invocation: true
---

# Repositórios pendentes de push

O workspace não é monorepo: a raiz e cada módulo são repositórios git separados. Esta skill
varre todos e mostra só os que têm alterações não commitadas.

## Passos

1. Rodar o script. Ele só lê o disco: não faz `git fetch` nem compara com o remoto do GitHub.

   ```bash
   bash "C:/eclipse-workspaces/ccp/.claude/skills/ccp-repos-pendentes-de-push/scripts/pendentes.sh"
   ```

2. Apresentar uma tabela Markdown só com os pendentes: **#** (contador
   iniciado em 1, incrementado a cada linha) | **Repositório** | **Modificados** |
   **Novos** | **Removidos**. Fechar com a linha de totais.
   As colunas vêm do `git status --porcelain`: **Novos** são os não rastreados (`??`),
   **Removidos** os que têm `D` no stage ou na árvore de trabalho, e **Modificados** todo o
   resto (editados, renomeados com `git mv`, adicionados ao stage). Somadas, as três dão o
   total de arquivos com mudança no repositório.
3. Destacar o repositório cuja branch é diferente de `main`.
4. Se houver pendentes, lembrar que o `fazPullEmTodosProjetosLocais.bat` faz `reset --hard`
   e descartaria esse trabalho.

As colunas "Commits à frente" e "Atrás" foram retiradas a pedido do usuário (2026-11-05):
exigiam um `git fetch` por repositório e deixavam o relatório lento. Por isso, um repositório
com commits locais ainda não enviados, mas sem alterações no disco, não aparece aqui.

## Restrições

- Somente leitura: nunca commitar, fazer push ou pull a partir desta skill.
- Se nada estiver pendente, responder em uma linha.
