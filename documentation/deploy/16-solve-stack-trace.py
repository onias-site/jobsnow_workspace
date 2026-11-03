# Comando /solveStackTrace: grava as sementes de 16-sementes-solve-stack-trace.jsonl (so as que faltam, com o mesmo id do
# ambiente local) e soma 1 na prioridade dos tickets abertos, pois o ticket de erro passou a ser o unico de prioridade 0.
# O deslocamento so roda quando o comando ainda nao existe: rodar de novo nao soma outra vez.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 16-solve-stack-trace.py [url] [--deslocar]
#      --deslocar forca a soma, para um ambiente onde as sementes ja chegaram por outro caminho.
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
force_shift = "--deslocar" in sys.argv
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def exists(index, document_id):
    try:
        call("GET", "/%s/_doc/%s" % (index, urllib.parse.quote(document_id, safe="")))
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


cluster = call("GET", "/")["cluster_name"]
print("cluster:", cluster)
seeds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "16-sementes-solve-stack-trace.jsonl")
with open(seeds_path, encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]

command_seeds = [seed for seed in seeds if seed["index"] == "jn_bot_command"]
if len(command_seeds) != 1:
    raise SystemExit("esperava 1 semente em jn_bot_command, achei %d" % len(command_seeds))
already_seeded = exists("jn_bot_command", command_seeds[0]["id"])

created = 0
for seed in seeds:
    if exists(seed["index"], seed["id"]):
        continue
    path = "/%s/_create/%s" % (seed["index"], urllib.parse.quote(seed["id"], safe=""))
    call("PUT", path, seed["source"])
    created += 1
print("sementes: %d no arquivo, %d criadas" % (len(seeds), created))

if already_seeded and not force_shift:
    print("comando ja existia: prioridades mantidas")
    raise SystemExit(0)

shift = {"script": {"lang": "painless", "source": "ctx._source.priority += 1"}, "query": {"exists": {"field": "priority"}}}
for index in ("jn_support_pending_command", "jb_pending_tickets"):
    result = call("POST", "/%s/_update_by_query?refresh=true&conflicts=proceed" % index, shift)
    print("%s: %d de %d tickets deslocados, %d falhas" % (index, result["updated"], result["total"], len(result["failures"])))
