# Token esquecido no /receberMensagens (2026-11-15): o texto que pede o token de login no comando /receiveMessages
# (/receberMensagens) do bot de usuario (VisUserReceiveMessagesMessages.askToken, pt e en, em jn_system_message, regra
# "igual") passa a ensinar, em linhas separadas, o comando /reenviarTokenDeLogin (/resendLoginToken) a quem esqueceu ou
# nao sabe onde esta o token. Pedido do usuario. Sementes em 87-sementes-token-esquecido-no-receber-mensagens.jsonl,
# mesmo _id do local (VisUserReceiveMessagesBotConfiguration, vis).
# Independe de deploy: so muda o texto. Idempotente.
# Cache das entidades: 1 h; publique nova revisao e reinicie os consumidores (pm2 restart all), ou espere a hora passar.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 87-token-esquecido-no-receber-mensagens.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 87-token-esquecido-no-receber-mensagens.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
failures = 0
with open(os.path.join(here, "87-sementes-token-esquecido-no-receber-mensagens.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-20s %s %s" % (index, seed["id"][:42], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
