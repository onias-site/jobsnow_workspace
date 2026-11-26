# Renomeia em portugues o comando /saveRecruiter do bot de suporte: /salvarRecrutador -> /salvarRh (pedido do usuario
# em 2026-11-26). O nome canonico (/saveRecruiter), o passo (VisSupportSaveRecruiter) e a fila
# JbBusinessRunBotCommand~support~saveRecruiter nao mudam: so o campo message do jn_bot_command_name em portugues
# (VisCommandNamesInPortuguese.saveRecruiter, semeado por VisEntityRecruiterSignUpReturn). O id do registro e o mesmo
# (chave commandName + language, regra "igual" ao local); o registro antigo de 79-sementes-comando-salvar-recrutador.jsonl
# e sobrescrito.
# Ordem: este script e depois o deploy dos consumidores (o bot le os comandos quando inicia; o cache da entidade dura 1 h).
# Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 127-comando-salvar-rh.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\127-comando-salvar-rh.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SEED = {
    "id": "462d38326cf12c9b1b2f40eb47a9fbc15f3bc6c8",
    "index": "jn_bot_command_name",
    "source": {"commandName": "saveRecruiter", "language": "portuguese", "message": "salvarRh"},
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
path = "/%s/_doc/%s" % (SEED["index"], urllib.parse.quote(SEED["id"], safe=""))
status, before = call("GET", path)
print("antes:", (before.get("_source") or {}).get("message"))
call("PUT", path + "?refresh=true", SEED["source"])
status, written = call("GET", path)
ok = status == 200 and written.get("_source") == SEED["source"]
print("depois:", (written.get("_source") or {}).get("message"), "ok" if ok else "FALHOU")
sys.exit(0 if ok else 1)
