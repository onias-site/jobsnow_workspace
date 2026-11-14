---
name: ccp-deploy
description: Faz deploy no Cloud Run do front, da API vis ou da API js, dos consumidores das filas na VM e do processo diário (Cloud Run Job), compilando antes as dependências na ordem dos pom.xml. Uso: /ccp-deploy front, /ccp-deploy vis, /ccp-deploy js, /ccp-deploy consumidores, /ccp-deploy cron, /ccp-deploy vis js ou /ccp-deploy todos. Use também sem o comando, quando o usuário pedir para publicar, subir, implantar ou levar para produção alguma alteração (ex. "faz o deploy", "sobe a js", "manda o front pra produção"), escolhendo os alvos pelos módulos alterados. Alvos - front, vis, js, consumidores, cron ou todos.
---

# Deploy no Cloud Run e na VM
Skill automática: avalia o contexto da conversa e executa o deploy dos alvos correspondentes sempre que identificar a necessidade e houver autorização do usuário. Os alvos são `front`, `vis`, `js`, `consumidores`, `cron` ou `todos` (os cinco), e pode haver mais de um. Sem alvo, responda com o uso em uma linha e não publique nada.

## Passo

Rode em segundo plano, passando os alvos recebidos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\eclipse-workspaces\ccp\.claude\skills\ccp-deploy\scripts\deploy.ps1" <alvos>
```

Ao terminar, informe por serviço: a revisão publicada, ou o erro exato. Se falhar, não tente de novo sem entender a causa.

## O que o script faz

| Alvo | Build | Publicação |
|---|---|---|
| `vis`, `js` | `mvn -pl <módulo> -am clean install -DskipTests`, na raiz | imagem no Cloud Build e nova revisão |
| `front` | o `npm run build` roda dentro da imagem, no Cloud Build | imagem no Cloud Build e nova revisão |
| `consumidores` | `mvn -pl ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser -am clean install -DskipTests`, junto com o build de vis e js | `documentation\deploy\07-publicar-na-vm.ps1 -SoConsumidores`: jar `-all` dos consumidores, `topicos.tsv` e demais arquivos da VM, PM2 reiniciado; o `cron.jar` da VM fica como está |
| `cron` | `mvn -pl ccp_cron-tasks_jobsnow -am clean install -DskipTests`, no mesmo build | `documentation\deploy\32-processo-diario-no-cloud-run.ps1`: imagem do jar `-all` no Cloud Build e o Cloud Run Job `jobsnow-processo-diario` atualizado; o agendamento fica pausado ou ligado como já estiver (o crontab da VM nunca foi instalado). Depois, `documentation\deploy\54-reenvio-do-token-de-login-no-cloud-run.ps1`: o mesmo jar no Cloud Run Job `jobsnow-reenvio-token-login` (de hora em hora) |

- Ordem da publicação: primeiro os serviços do Cloud Run, depois os consumidores, por último o processo diário. Uma falha interrompe os passos seguintes.
- Ao terminar os consumidores e o processo diário, informe que foram publicados (a imagem do job aparece na situação do 32) ou o erro exato.
- A ordem de build vem do `-am`, que lê os `pom.xml`, então acompanha qualquer mudança de dependência.
- Para ver a ordem sem compilar nem publicar: acrescente `-SoListar` ao comando.
- Acesso público ou privado e instância mínima de cada serviço não mudam.
- As propriedades não mudam. Para publicar `C:\segredos\producao.json`, use `documentation\deploy\08-publicar-cloud-run.ps1 -SoSegredo`.

## Restrições

- Nunca exiba valores de segredos nem imprima o conteúdo de `C:\segredos\producao.json`.
- Os testes não rodam neste comando: o código vai para produção como está no disco, inclusive o que não foi commitado.
- Não rode junto com a suíte de testes nem perto das 10:00, quando a cobertura trava `target`.
- Não rode em `todos` sem o usuário pedir: publicar a vis e a js antes dos dados contraria o plano de migração enquanto ele não terminar.
- Não faz commit nem push.
