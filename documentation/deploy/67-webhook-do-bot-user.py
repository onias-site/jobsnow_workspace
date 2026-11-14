# Webhook do bot user em producao (2026-11-13).
# O JnBusinessHandleBotUpdate (fila JnBusinessHandleBotUpdate~user) procura em jn_bot_update_handler o business que
# trata os updates pelo nome do bot. Ate hoje so o support tinha o registro (semente do JbEntityBot, jb 22cf9d4), e o
# bot user recebia so por polling local. Este script grava em producao o registro do user, com o mesmo _id do local
# (sha1 do botName, regra "igual"), e confere relendo. Idempotente.
# Roda ANTES do setWebhook do bot user (o webhook publica na fila e o consumidor precisa achar o tratador).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 67-webhook-do-bot-user.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 67-webhook-do-bot-user.py
import hashlib
import json
import os
import sys
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

INDEX = "jn_bot_update_handler"
RECORD = {"botName": "user", "business": "com.jb.business.bots.engine.JbBusinessReceiveBotUpdate"}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request) as response:
        return json.load(response)


record_id = hashlib.sha1(RECORD["botName"].encode("utf-8")).hexdigest()
call("PUT", "/" + INDEX + "/_doc/" + record_id + "?refresh=true", RECORD)
stored = call("GET", "/" + INDEX + "/_doc/" + record_id)
ok = stored.get("found") and stored["_source"] == RECORD
print(("OK " if ok else "FALHOU ") + INDEX + " " + record_id + " " + json.dumps(stored.get("_source")))
sys.exit(0 if ok else 1)
