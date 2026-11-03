---
name: ccp-deploy
description: Faz deploy no Cloud Run do front, da API vis ou da API js, compilando antes as dependências na ordem dos pom.xml. Uso: /ccp-deploy front, /ccp-deploy vis, /ccp-deploy js, /ccp-deploy vis js ou /ccp-deploy todos.
disable-model-invocation: true
---

# Deploy no Cloud Run

Comando manual: só roda quando o usuário digitar `/ccp-deploy <alvo>`. Os alvos são `front`, `vis`, `js` ou `todos`, e pode haver mais de um. Sem alvo, responda com o uso em uma linha e não publique nada.

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

- A ordem de build vem do `-am`, que lê os `pom.xml`, então acompanha qualquer mudança de dependência.
- Para ver a ordem sem compilar nem publicar: acrescente `-SoListar` ao comando.
- Acesso público ou privado e instância mínima de cada serviço não mudam.
- As propriedades não mudam. Para publicar `C:\segredos\producao.json`, use `documentation\deploy\08-publicar-cloud-run.ps1 -SoSegredo`.

## Restrições

- Nunca exiba valores de segredos nem imprima o conteúdo de `C:\segredos\producao.json`.
- Os testes não rodam neste comando: o código vai para produção como está no disco, inclusive o que não foi commitado.
- Não rode junto com a suíte de testes nem perto das 12:00, quando a cobertura trava `target`.
- Não rode em `todos` sem o usuário pedir: publicar a vis e a js antes dos dados contraria o plano de migração enquanto ele não terminar.
- Não faz commit nem push.
