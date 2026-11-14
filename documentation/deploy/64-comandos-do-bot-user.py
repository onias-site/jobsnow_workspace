# Comandos do bot user (2026-11-12):
#   /receiveMessages <email>  (vis): pede o token de login do e-mail; o certo grava o chatId no curriculo (ativo ou
#                             inativo); o errado conta em vis_login_token_attempts e, na terceira vez, bloqueia o chat.
#   /resendLoginToken <email> (js): faz o mesmo pedido de reenvio do token da tela de login e responde como ela.
# Este script leva a producao:
#   1. o indice novo vis_login_token_attempts (VisEntityLoginTokenAttempts), com o mapeamento do arquivo de criacao do
#      local;
#   2. as sementes de 64-sementes-comandos-do-bot-user.jsonl (com o mesmo id do local, regra "igual"): os 2 comandos com
#      passos, nomes em portugues, explicacoes, mensagens de fim, os textos (jn_system_message) e o validador loginToken
#      de jn_session_validator (JsBusinessCheckTypedLoginToken, que o vis roda pelo nome da classe).
# Roda ANTES do deploy da API vis, da API js e dos consumidores, junto com as filas novas do 03-criar-filas.ps1
# (JbBusinessRunBotCommand~user~receiveMessages e ~user~resendLoginToken). Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 64-comandos-do-bot-user.py [destino] [--sem-sementes]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 64-comandos-do-bot-user.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
without_seeds = "--sem-sementes" in sys.argv
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_dir = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                          "elasticsearch", "scripts", "entities", "create")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

NEW_INDEX = "vis_login_token_attempts"


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

# 1. indice novo
with open(os.path.join(create_dir, NEW_INDEX), encoding="utf-8") as source:
    definition = json.load(source)
status, _ = call("HEAD", "/" + NEW_INDEX)
if status == 404:
    status, answer = call("PUT", "/" + NEW_INDEX, definition)
    print("criado %s: %s" % (NEW_INDEX, status))
status, mapping = call("GET", "/%s/_mapping" % NEW_INDEX)
mappings = mapping[NEW_INDEX]["mappings"]
same = mappings.get("properties") == definition["mappings"]["properties"] and mappings.get("dynamic") == "strict"
failures += 0 if same else 1
print("%-28s mapeamento igual ao local: %s" % (NEW_INDEX, same))

# 2. sementes
if without_seeds:
    sys.exit(1 if failures else 0)
with open(os.path.join(here, "64-sementes-comandos-do-bot-user.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    status, answer = call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-42s %s %s" % (index, seed["id"][:40], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
