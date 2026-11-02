# Ligar o bot de produção

Roteiro escrito em 2026-11-01. Troque `login.seudominio.com.br` pelo endereço real da API js.

Em produção, o Telegram entrega as mensagens em `POST /telegram-webhook/{botName}`, na API js. O bot roda dentro dessa requisição. O polling (`JbInstantMessengerReaderStarter`) continua existindo, mas só para testes locais.

**Decisão: usar um bot só para produção e outro para testes locais.** O Telegram não entrega por webhook e por polling ao mesmo tempo: com webhook ativo, o `getUpdates` daquele token responde 409. Com dois bots, cada ambiente fica com o seu token e o polling local continua funcionando.

**O que já foi testado:** o webhook na API local, com chamadas simuladas e cache em memória. **O que nunca foi testado:** o registro no Telegram real, o Cloud Run e a API rodando com `localEnvironment` falso.

## Antes de começar

Estes itens impedem o bot de funcionar e precisam estar resolvidos primeiro.

| # | Requisito | Situação em 2026-11-01 |
|---|---|---|
| 1 | API js publicada com HTTPS público | Pendente; ver `ligar-dominio-kinghost-ao-gcp.md`, que prevê `login.seudominio.com.br` no Cloud Run, sem Dockerfile para as APIs Java. |
| 2 | Cache que funcione onde a API roda | Pendente. Fora do ambiente local, a API usa `CcpGcpMemoryStore`, sobre o Memorystore for Valkey com endpoint único (cluster mode disabled), sem autenticação nem TLS. Crie a instância, informe `memorystore.host` e `memorystore.port` em `application_properties` e ligue o Cloud Run à VPC por Direct VPC egress. Só foi testado contra um servidor falso do protocolo, nunca contra um Valkey real. |
| 3 | Elasticsearch de produção acessível pela API, com índices e sementes | Pendente; hoje só existe o local. |
| 4 | Pub/Sub e consumidor publicados | Pendente; fora do ambiente local, a API publica no Pub/Sub. Não foi conferido quais comandos do bot dependem disso. |

A porta também precisa ser conferida: o `application.properties` fixa `server.port=8082`. No Cloud Run, use `--port=8082`, como no roteiro do domínio.

## Passo a passo

**1. Crie o bot de produção.** No Telegram, fale com o @BotFather, envie `/newbot` e guarde o token. Não coloque o token em arquivo versionado.

**2. Gere o segredo do webhook.** Ele não tem relação com o token e não deve ser reaproveitado de outro ambiente:

```powershell
$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
-join ($b | ForEach-Object { $_.ToString('x2') })
```

**3. Monte as propriedades de produção.** O `application_properties` da API precisa ter, além do que ela já usa:

```json
{
  "localEnvironment": false,
  "bots": { "support": "TOKEN_DO_BOT_DE_PRODUCAO" },
  "telegramWebhookSecrets": { "support": "SEGREDO_DO_PASSO_2" }
}
```

Sem `telegramWebhookSecrets`, a API recusa todas as chamadas com 401 e o registro falha. Guarde um JSON completo em um arquivo **fora do repositório**, por exemplo `C:\segredos\producao.json`. Ele será usado no passo 8.

**4. Crie os índices e as sementes.** No Elasticsearch de produção, confira se estes itens existem:

| Índice | O que precisa ter |
|---|---|
| `jn_bot_update_handler` | Um registro com `botName = support`, apontando para `JbBusinessReceiveBotUpdate`. |
| `jb_bot_allowed_user` | Os `chatId` dos operadores. A semente traz apenas `751717896`. |
| `jb_bot_update_id` | Pode ficar vazio. |
| `jn_bot_*` e `jb_bot*` | Comandos, passos e textos do bot. |

`CcpCreateEntities` grava essas sementes, mas **apaga os índices antes de recriá-los**. Só rode em um banco vazio e confira o endereço do Elasticsearch antes.

**5. Publique a API js** com as propriedades do passo 3. Não rode `JbInstantMessengerReaderStarter` em produção.

Use `--min-instances=1` no Cloud Run: a primeira mensagem carrega o motor do bot, e isso levou 3 segundos no teste local, sem contar a subida da API.

**6. Confira que a API responde e recusa estranhos.** Esta chamada não tem segredo, então deve voltar **401**:

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" -X POST https://login.seudominio.com.br/telegram-webhook/support -H "Content-Type: application/json" -d "{\`"update_id\`":1}"
```

| Resposta | Significado |
|---|---|
| 401 | Certo. |
| 404 | A rota não chega à API js; confira o load balancer e a versão publicada. |
| 200 | **Pare:** a chamada foi aceita sem segredo. |

**7. Confira os operadores.** Cada um precisa estar em `jb_bot_allowed_user`, senão não usa os comandos do suporte. Em conversa privada, o `chatId` é o id da conta no Telegram, então ele é o mesmo no bot de testes e no de produção.

**8. Registre o webhook.** O starter usa o `application_properties` do processo, então carregue o arquivo do passo 3 apenas neste terminal:

```powershell
Set-Location C:\eclipse-workspaces\ccp\js_rest-api_spring_jobsnow_dependency-chooser
mvn -o -q dependency:build-classpath "-Dmdep.outputFile=target\cp.txt"
$env:CLASSPATH = "target\classes;" + (Get-Content target\cp.txt -Raw).Trim()
$env:application_properties = Get-Content C:\segredos\producao.json -Raw
java com.js.rest.api.telegram.JsTelegramWebhookStarter register support https://login.seudominio.com.br
```

O endereço vai sem o caminho e precisa usar a porta 443, 80, 88 ou 8443. A resposta esperada traz `ok` verdadeiro e `Webhook was set`.

**9. Confira o que o Telegram registrou,** no mesmo terminal:

```powershell
$p = $env:application_properties | ConvertFrom-Json
Invoke-RestMethod "https://api.telegram.org/bot$($p.bots.support)/getWebhookInfo" | Select-Object -ExpandProperty result
```

| Campo | Valor esperado |
|---|---|
| `url` | `https://login.seudominio.com.br/telegram-webhook/support` |
| `max_connections` | `1` |
| `allowed_updates` | `message` |
| `last_error_message` | Vazio |
| `pending_update_count` | `0`, ou caindo |

**10. Teste com o bot.** Faça nesta ordem:

| Envie | Resultado esperado |
|---|---|
| `/chatId` | O bot responde o seu `chatId`. |
| `/ticketsPendentes` | Mostra a lista de tickets ou avisa que não há nenhum. |
| `2`, se houver mais de um ticket | Vai para o próximo: prova que a sessão entre mensagens funciona. |
| `/sair` | Encerra a sessão. |

Esse teste exercita o cache de produção, que nunca foi testado. Se o `2` não avançar, confira o cache primeiro.

**11. Limpe o terminal.** Feche-o, ou rode:

```powershell
Remove-Item env:application_properties, env:CLASSPATH
Remove-Item target\cp.txt
```

Mova `C:\segredos\producao.json` para um cofre de senhas, ou apague-o se os valores já estiverem guardados em outro lugar.

## Como desligar

Rode os comandos do passo 8, trocando a última linha por:

```powershell
java com.js.rest.api.telegram.JsTelegramWebhookStarter delete support
```

As mensagens ainda não entregues ficam guardadas no Telegram e podem ser lidas por polling. Só rode o polling com esse token depois de desligar o webhook.

## Quando trocar algo

| Mudança | O que fazer |
|---|---|
| Novo endereço da API | Passos 8 e 9. |
| Novo segredo | Atualize a propriedade, publique a API e repita os passos 8 e 9. Até o novo registro, as chamadas dão 401, e o Telegram tenta de novo depois. |
| Token vazado | Revogue-o no @BotFather com `/revoke`, atualize `bots.support` e publique a API. Depois repita os passos 8 e 9. |
| Segredo vazado | Trate como invasão: com ele, é possível se passar por qualquer operador. Troque-o na hora e confira os tickets resolvidos no período. |
| Novo operador | Inclua o `chatId` em `jb_bot_allowed_user` e **reinicie a API**: a lista é carregada na memória quando o bot sobe. |

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `last_error_message` com `401` | O segredo registrado não é o que está na API; repita o passo 8 com as mesmas propriedades publicadas. |
| `last_error_message` com `500` | Um passo do bot falhou; veja `jn_jobsnow_error`. O Telegram reenvia, mas a reentrega é ignorada e a fila segue. |
| `pending_update_count` subindo | A API está fora do ar ou lenta. |
| O bot recebe, mas não responde a um comando do suporte | O `chatId` não está em `jb_bot_allowed_user`, ou a API não foi reiniciada depois de incluí-lo. |
| O `getUpdates` responde 409 | O webhook desse token está ativo; desligue-o ou use o bot de testes. |
| Mensagem perdida depois de um erro | Comportamento previsto: o offset é gravado antes de o bot rodar, para um comando nunca executar duas vezes. O operador deve reenviar. |
| `ArrayIndexOutOfBoundsException` no starter | Faltaram argumentos. |
