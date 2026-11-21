# Parametros do sistema: cria no destino o indice jn_system_parameter (JnEntitySystemParameter, os mesmos campos de
# jn_system_message sem o language) e recorta para ele os dois registros de jn_system_message que falseavam o language
# (gravados so em portuguese, mas listas que nao dependem de idioma):
#   NONPROFESSIONALDOMAINS                                  -> NONPROFESSIONALDOMAINS
#   com.vis.business.telegram.VisTelegramSystemMessages.groups -> com.vis.business.telegram.VisTelegramSystemParameters.groups
# (o enum dos grupos do Telegram foi renomeado: deixou de ser mensagem do sistema). O conteudo (message) vem do proprio
# destino, que e a fonte da verdade; o id novo e o SHA-1 do systemMessageName, como em CcpEntity.calculateId
# (hexadecimal com sinal, sem zeros a esquerda).
#
# Duas fases, por causa do deploy:
#   copiar          ANTES do deploy da vis, dos consumidores e do cron: cria o indice (se faltar) e grava os 2 registros
#                   novos. Os registros antigos ficam, e a versao ainda no ar continua lendo-os.
#   apagar-antigos  DEPOIS do deploy: apaga de jn_system_message os 2 registros antigos, so quando o novo existe com a
#                   mesma lista.
# Idempotente: rodar de novo regrava os novos com a lista do antigo (enquanto ele existir) e ignora o que ja foi apagado.
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 105-parametros-do-sistema.py copiar|apagar-antigos [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPING = os.path.join(HERE, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "jn", "database",
                       "elasticsearch", "scripts", "entities", "create", "jn_system_parameter")
OLD_INDEX = "jn_system_message"
NEW_INDEX = "jn_system_parameter"
MOVES = [
    ("NONPROFESSIONALDOMAINS", "NONPROFESSIONALDOMAINS"),
    ("com.vis.business.telegram.VisTelegramSystemMessages.groups", "com.vis.business.telegram.VisTelegramSystemParameters.groups"),
]

if len(sys.argv) < 2 or sys.argv[1] not in ("copiar", "apagar-antigos"):
    raise SystemExit("uso: python 105-parametros-do-sistema.py copiar|apagar-antigos [url do destino]")
phase = sys.argv[1]
target_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, missing_ok=False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise SystemExit("%s %s %s: %s" % (method, path, error.code, error.read().decode("utf-8", "replace")[:600]))


def entity_id(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    # CcpHashDecorator: new BigInteger(digest).toString(16), com sinal e sem zeros a esquerda
    return format(int.from_bytes(digest, "big", signed=True), "x")


def old_records(name):
    query = {"size": 10, "query": {"term": {"systemMessageName": name}}}
    return call("POST", "/%s/_search" % OLD_INDEX, query)["hits"]["hits"]


def new_record(name):
    found = call("GET", "/%s/_doc/%s" % (NEW_INDEX, entity_id(name)), missing_ok=True)
    return found["_source"] if found and found.get("found") else None


print("destino:", call("GET", "/")["cluster_name"], "| fase:", phase)

if phase == "copiar":
    if call("GET", "/" + NEW_INDEX, missing_ok=True) is None:
        with open(MAPPING, encoding="utf-8") as mapping_file:
            mapping = json.load(mapping_file)
        call("PUT", "/" + NEW_INDEX, mapping)
        print("indice criado:", NEW_INDEX)
    for old_name, new_name in MOVES:
        olds = old_records(old_name)
        if not olds:
            if new_record(new_name) is None:
                raise SystemExit("%s: nao existe nem em %s nem em %s" % (old_name, OLD_INDEX, NEW_INDEX))
            print("%s: antigo ja apagado, novo presente" % new_name)
            continue
        if len(olds) > 1:
            raise SystemExit("%s: %d registros em %s (esperado 1)" % (old_name, len(olds), OLD_INDEX))
        message = olds[0]["_source"]["message"]
        record = {"systemMessageName": new_name, "message": message}
        result = call("PUT", "/%s/_doc/%s?refresh=true" % (NEW_INDEX, entity_id(new_name)), record)
        print("%s -> %s/%s: %s, %d itens" % (old_name, NEW_INDEX, entity_id(new_name), result["result"], len(message)))
        if new_record(new_name)["message"] != message:
            raise SystemExit("%s: conferencia falhou" % new_name)

if phase == "apagar-antigos":
    for old_name, new_name in MOVES:
        created = new_record(new_name)
        if created is None:
            raise SystemExit("%s: o novo nao existe em %s; rode a fase copiar" % (new_name, NEW_INDEX))
        for old in old_records(old_name):
            if old["_source"]["message"] != created["message"]:
                raise SystemExit("%s: lista diferente da de %s; rode a fase copiar de novo" % (old_name, NEW_INDEX))
            call("DELETE", "/%s/_doc/%s?refresh=true" % (OLD_INDEX, old["_id"]))
            print("apagado de %s: %s (%s)" % (OLD_INDEX, old_name, old["_source"].get("language")))
        print("%s: nenhum registro antigo restante" % old_name if not old_records(old_name) else "SOBROU %s" % old_name)

print("total em %s:" % NEW_INDEX, call("GET", "/%s/_count" % NEW_INDEX)["count"])
