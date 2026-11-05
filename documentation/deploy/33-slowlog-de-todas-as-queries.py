# Liga ou desliga o registro de TODAS as queries no slowlog do Elasticsearch (limite de 0 ms) nos indices jn_*, vis_*,
# js_*, jb_*: buscas (fases query e fetch, uma linha por shard) e escritas (uma linha por documento, sem o documento:
# index.indexing.slowlog.source = 0). Com ele ligado, os paineis 27 (requisicoes do Cloud Run) e 29 (filas do Pub/Sub)
# mostram o tempo de cada query por dentro do Elasticsearch, ligado a requisicao ou a mensagem pelo trace id que o
# ElasticSearchDbRequester manda em cada chamada (traceparent e X-Opaque-Id). Desligado, os limites voltam ao padrao
# (-1, nada registrado) e os paineis mostram so a latencia medida pelo cliente.
# O slowlog de busca grava o corpo da query, que pode ter e-mails: vai para o disco da VM e para o Cloud Logging (log
# elasticsearch_slowlog, ver 23-ops-agent-na-vm.sh). Ligue para investigar e desligue depois.
# Indice criado depois de ligar nao herda o limite: rode "ligar" de novo.
# Uso: powershell -ExecutionPolicy Bypass -File com-tunel-de-producao.ps1 -Script 33-slowlog-de-todas-as-queries.py -Argumentos ligar
#      (ou desligar, ou situacao); no local: python -X utf8 33-slowlog-de-todas-as-queries.py ligar http://localhost:9200
import json
import os
import sys
import urllib.request

ACTIONS = ("ligar", "desligar", "situacao")
action = sys.argv[1] if len(sys.argv) > 1 else "situacao"
if action not in ACTIONS:
    sys.exit("uso: 33-slowlog-de-todas-as-queries.py %s [url]" % "|".join(ACTIONS))
url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
INDICES = "jn_*,vis_*,js_*,jb_*"
SETTINGS = {
    "index.search.slowlog.threshold.query.trace": "0ms",
    "index.search.slowlog.threshold.fetch.trace": "0ms",
    "index.indexing.slowlog.threshold.index.trace": "0ms",
    "index.indexing.slowlog.source": "0",
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def situation():
    names = ",".join(SETTINGS)
    # o _settings filtrado so traz os indices que tem a configuracao gravada: a lista vem do _cat
    indices = [item["index"] for item in call("GET", "/_cat/indices/%s?h=index&format=json" % INDICES)]
    found = call("GET", "/%s/_settings/%s?flat_settings=true" % (INDICES, names))
    on = sorted(index for index, item in found.items() if item.get("settings", {}).get("index.search.slowlog.threshold.query.trace") == "0ms")
    off = sorted(index for index in indices if index not in on)
    print("indices com todas as queries no slowlog: %d; sem: %d" % (len(on), len(off)))
    for index in off if on else []:
        print("  sem:", index)


print("cluster:", call("GET", "/")["cluster_name"])
if action == "ligar":
    print(call("PUT", "/%s/_settings" % INDICES, SETTINGS))
if action == "desligar":
    print(call("PUT", "/%s/_settings" % INDICES, {name: None for name in SETTINGS}))
situation()
