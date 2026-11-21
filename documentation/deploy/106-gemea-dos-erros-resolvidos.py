# Gemea dos erros resolvidos: cria no destino o indice jn_jobsnow_error_solved (gemea de JnEntityJobsnowError, com o
# mesmo mapeamento de jn_jobsnow_error, como faz o CcpCreateEntities com toda gemea) e move para ela o unico registro de
# jn_jobsnow_error: grava com o mesmo _id na gemea, confere e so entao apaga da principal.
#
# Roda ANTES do deploy das APIs, dos consumidores e do cron com a gemea (a versao nova le e escreve nos dois indices).
# Idempotente: indice existente nao e recriado; com a principal ja vazia e o registro na gemea, so confere.
# Aborta se a principal tiver mais de 1 registro (o pedido foi mover o unico).
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 106-gemea-dos-erros-resolvidos.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MAPPING = os.path.join(HERE, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "jn", "database",
                       "elasticsearch", "scripts", "entities", "create", "jn_jobsnow_error")
MAIN_INDEX = "jn_jobsnow_error"
TWIN_INDEX = "jn_jobsnow_error_solved"

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
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


def documents(index):
    return call("POST", "/%s/_search" % index, {"size": 10, "query": {"match_all": {}}})["hits"]["hits"]


print("destino:", call("GET", "/")["cluster_name"])

if call("GET", "/" + TWIN_INDEX, missing_ok=True) is None:
    with open(MAPPING, encoding="utf-8") as mapping_file:
        mapping = json.load(mapping_file)
    call("PUT", "/" + TWIN_INDEX, mapping)
    print("indice criado:", TWIN_INDEX)
else:
    print("indice ja existia:", TWIN_INDEX)

mains = documents(MAIN_INDEX)
if len(mains) > 1:
    raise SystemExit("%s tem %d registros (esperado 1); nada foi movido" % (MAIN_INDEX, len(mains)))

for document in mains:
    doc_id = document["_id"]
    source = document["_source"]
    result = call("PUT", "/%s/_doc/%s?refresh=true" % (TWIN_INDEX, doc_id), source)
    copied = call("GET", "/%s/_doc/%s" % (TWIN_INDEX, doc_id), missing_ok=True)
    if not copied or not copied.get("found") or copied["_source"] != source:
        raise SystemExit("%s: conferencia na gemea falhou; a principal ficou intacta" % doc_id)
    call("DELETE", "/%s/_doc/%s?refresh=true" % (MAIN_INDEX, doc_id))
    print("movido %s -> %s: %s (%s: %s)" % (doc_id, TWIN_INDEX, result["result"], source.get("type"),
                                           (source.get("message") or "")[:80]))

main_count = call("GET", "/%s/_count" % MAIN_INDEX)["count"]
twin_count = call("GET", "/%s/_count" % TWIN_INDEX)["count"]
print("total em %s: %d | total em %s: %d" % (MAIN_INDEX, main_count, TWIN_INDEX, twin_count))
if main_count != 0:
    raise SystemExit("SOBROU registro em %s" % MAIN_INDEX)
