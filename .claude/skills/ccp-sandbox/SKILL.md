---
name: ccp-sandbox
description: Sobe, para, atualiza ou mostra o estado do sandbox de testes manuais — uma cópia congelada do ambiente local (Elasticsearch 9201, API vis 18081, API js 18082, front end 3100 e leitor de um bot de suporte próprio no Telegram) que não é afetada pelas alterações de código feitas no workspace. Use quando pedirem "suba o sandbox", "pare o sandbox", "atualize o código do sandbox", "copie os dados de novo para o sandbox", "o sandbox está no ar?", ou quando o usuário quiser continuar testando enquanto o código muda.
---

# Sandbox de testes manuais

Tudo é feito pelo script `scripts/sandbox.ps1`, que fica ao lado deste arquivo. O sandbox mora em `C:\jobsnow-sandbox` e
roda em paralelo ao ambiente de desenvolvimento (ES 9200, vis 8081, js 8082, front 3000), sem disputar porta nem dado.

| Peça | Sandbox | Desenvolvimento |
|---|---|---|
| Elasticsearch | `http://localhost:9201` (transporte 9301) | 9200 |
| API vis | `http://localhost:18081` | 8081 |
| API js (login) | `http://localhost:18082` | 8082 |
| Front end | `http://localhost:3100` | 3000 |
| Bot de suporte | bot próprio (token em `C:\jobsnow-sandbox\sandbox-config.json`) | bot `support` do `application_properties` |

## Como executar

Rode o script com o PowerShell, em segundo plano (a primeira subida leva alguns minutos):

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\eclipse-workspaces\ccp\.claude\skills\ccp-sandbox\scripts\sandbox.ps1" -Action <ação> *> "<scratch>\sandbox.log"
```

| Pedido do usuário | `-Action` | O que faz |
|---|---|---|
| "suba o sandbox" | `start` | Sobe o que estiver parado. Na primeira vez também tira o snapshot do código e do front e copia os dados. |
| "pare o sandbox" | `stop` | Para tudo, inclusive o ES do sandbox. Os dados e o código copiados ficam guardados. |
| "o sandbox está no ar?" | `status` | Mostra cada peça, quando o código foi copiado e quando os dados foram copiados. |
| "atualize o código do sandbox" | `refresh-code` | Para as APIs, o bot e o front e tira um novo snapshot do workspace **como ele estiver agora**. Depois sobe tudo de novo. |
| "copie os dados de novo" | `refresh-data` | Apaga os índices `jn_*`, `jb_*` e `vis_*` do sandbox e restaura um snapshot novo do ES 9200. Também reinicia as APIs, que têm cache em memória. |

Depois, leia o log e informe ao usuário a tabela de estado que o script imprime no fim. Se alguma peça não subir, leia
`C:\jobsnow-sandbox\logs\<peça>.log` (`es`, `vis-api`, `js-api`, `bot`, `front`).

Os processos são criados pelo WMI, fora da sessão do Claude: **continuam no ar depois de um `/clear` ou do fim da
sessão**, até um `stop` ou até o computador reiniciar. Depois de reiniciar o computador, basta um `start`.

## O que fica isolado e o que não fica

- **Código**: as classes e os jars de cada aplicação são copiados para `C:\jobsnow-sandbox\code` no snapshot. Um
  `mvn install` no workspace não muda nada no sandbox até um `refresh-code`. O snapshot usa os jars do `~/.m2` **como
  estão no momento** (o mesmo critério da skill `ccp-subir-apis-e-recriar-entidades`). Se houver módulo alterado e
  ainda não instalado, instale antes de tirar o snapshot.
- **Front**: o código é copiado para `C:\jobsnow-sandbox\front`, com `localhost:8080`/`8081`/`8082` trocados por
  `18080`/`18081`/`18082`. O `node_modules` **não é copiado**: é uma junção para o do workspace. Se uma alteração mexer nas
  dependências do front (`npm install`), o sandbox passa a usar as novas.
- **Dados**: o ES do sandbox tem pasta de dados própria (`C:\jobsnow-sandbox\es\data`). Só os índices `jn_*`, `jb_*`
  e `vis_*` são copiados, pelo repositório de snapshot `jobsnow_sandbox` (`C:\jn\snapshots\jobsnow-sandbox`). Recriar
  índices no 9200 (CcpCreateEntities) não afeta o sandbox. Os índices legados sem prefixo não são copiados.
- **Login**: o front 3100 tem o próprio `localStorage`, porque a porta é outra. O login é feito de novo no sandbox.
- **Telegram**: dois leitores não podem ler o mesmo bot ao mesmo tempo, porque o Telegram recusa o segundo. Por isso o
  sandbox usa outro bot, criado no @BotFather. O token fica em `supportBotToken` no `sandbox-config.json`, fora do
  repositório. Sem token, o sandbox sobe sem o leitor do bot e avisa. Depois de criar o bot, o usuário precisa mandar
  `/start` para ele uma vez. Na cópia de dados, o offset de leitura (`jb_bot_update_id`) é apagado, porque o offset
  copiado pertence ao bot de desenvolvimento.
- **Não isolado — `c:\logs`**: o caminho está fixo no código. Os dois ambientes gravam nas mesmas pastas: e-mails
  (`c:\logs\email`, de onde sai o token de login), marcas de exclusão do cache (`c:\logs\cache\deleted-keys`, o que só
  causa releituras a mais) e arquivos de bucket. Avise o usuário quando ele for buscar um token de e-mail com os dois
  ambientes em uso: o arquivo mais recente pode ser do outro ambiente.

## Recursos

O ES do sandbox usa 1 GB de heap (o `jvm.options` da instalação compartilhada `C:\elasticsearch-7.4.0`). Cada API e o
leitor do bot são uma JVM a mais, e o front é um `next dev` a mais.
