# Registra o webhook do bot user de producao (@onias_site_user_prd_bot) em https://login.onias.site/telegram-webhook/user
# (2026-11-13). Ate hoje so o bot support tinha webhook; o user nao recebia nada em producao. Passos, em ordem:
#   1. 67-webhook-do-bot-user.py pelo tunel: grava o tratador do user em jn_bot_update_handler (sem ele o consumidor da
#      fila JnBusinessHandleBotUpdate~user falha em toda mensagem);
#   2. acrescenta ao C:\segredos\producao.json o segredo do user em telegramWebhookSecrets (aleatorio, 64 hex, nunca
#      exibido; se ja existir, fica o que esta la): sem ele a API js recusa todo POST do webhook do user;
#   3. 08-publicar-cloud-run.ps1 -SoSegredo -Servicos js: guarda as propriedades no Secret Manager e publica revisao nova
#      da js com a mesma imagem (a js le o segredo ao subir);
#   4. setWebhook no Telegram com o token e o segredo do producao.json, allowed_updates=[message], max_connections=1 (os
#      mesmos do support, JsBusinessRegisterTelegramWebhook), e mostra o getWebhookInfo.
# Idempotente. Para desfazer: deleteWebhook do bot user (o polling local usa outro bot, nao e afetado).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File 68-webhook-do-bot-user.ps1
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$properties = 'C:\segredos\producao.json'

'== 1. tratador do bot user em jn_bot_update_handler'
& (Join-Path $here 'com-tunel-de-producao.ps1') -Script (Join-Path $here '67-webhook-do-bot-user.py')

'== 2. segredo do webhook do bot user'
$addSecret = @'
import json, re, secrets, shutil, sys
path = sys.argv[1]
text = open(path, "rb").read().decode("utf-8-sig")
properties = json.loads(text)
if properties["telegramWebhookSecrets"].get("user"):
    print("segredo do user ja existe, mantido")
    sys.exit(0)
# insercao no texto, depois do segredo do support, para manter a formatacao do resto do arquivo
match = re.search(r'("telegramWebhookSecrets"\s*:\s*\{(\s*))("support"\s*:\s*"[^"]*")', text)
if not match:
    sys.exit("formato de telegramWebhookSecrets nao reconhecido; nada alterado")
indentation = match.group(2)
new_entry = match.group(3) + "," + indentation + '"user":  "' + secrets.token_hex(32) + '"'
changed = text[:match.start(3)] + new_entry + text[match.end(3):]
if json.loads(changed)["telegramWebhookSecrets"].get("user") is None:
    sys.exit("insercao invalida; nada alterado")
shutil.copy2(path, path + ".antes-do-webhook-user")
open(path, "wb").write(changed.encode("utf-8"))
print("segredo do user gravado (copia anterior em " + path + ".antes-do-webhook-user)")
'@
$addSecret | & python -I - $properties
if ($LASTEXITCODE -ne 0) { throw 'o segredo nao foi gravado' }

'== 3. revisao nova da API js com as propriedades'
# o 08 roda o gcloud, que escreve avisos no stderr: com Stop o PowerShell 5.1 os trata como erro fatal
$ErrorActionPreference = 'Continue'
& (Join-Path $here '08-publicar-cloud-run.ps1') -SoSegredo -Servicos js
$revision = & (Join-Path $env:LOCALAPPDATA 'Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd') run services describe jobsnow-js --project=jobsnow-prd --region=southamerica-east1 '--format=value(status.latestReadyRevisionName)' 2>$null
"revisao pronta da js: $revision"
$ErrorActionPreference = 'Stop'

'== 4. setWebhook do bot user'
$register = @'
import json, sys, urllib.request
properties = json.load(open(sys.argv[1], encoding="utf-8-sig"))
token = properties["bots"]["user"]
secret = properties["telegramWebhookSecrets"]["user"]
base = properties.get("urlInstantMessengerKey") or "https://api.telegram.org/bot"
body = {"url": "https://login.onias.site/telegram-webhook/user", "secret_token": secret,
        "allowed_updates": ["message"], "max_connections": 1}
request = urllib.request.Request(base + token + "/setWebhook", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
print("setWebhook:", json.load(urllib.request.urlopen(request)).get("description"))
info = json.load(urllib.request.urlopen(base + token + "/getWebhookInfo"))["result"]
print("url:", info.get("url"), "| pendentes:", info.get("pending_update_count"), "| max_connections:",
      info.get("max_connections"), "| updates:", info.get("allowed_updates"), "| ultimo erro:", info.get("last_error_message"))
'@
$register | & python -I - $properties
