# Apaga o indice jn_versionable depois que o historico de cada registro versionavel foi levado para o jn_grouper
# (2026-11-20; um grupo por registro e entidade, parentName jn_virtual_versionable_history, gravado pelo
# MoveVersionableHistoryToGrouper.java). So apaga com --apagar e quando:
#   1. o MoveVersionableHistoryToGrouper.java --conferir acabou de sair com 0 (o .ps1 so chama este script nesse caso);
#   2. ha um snapshot SUCCESS do repositorio (jobsnow-backup) das ultimas 36 horas que contem o jn_versionable.
# Sem --apagar so mostra as contagens. Sem argumento usa o tunel (http://127.0.0.1:9210) e ES_DESTINO_AUTH.
# Uso: python -I 104-historico-versionavel-no-grouper.py [url] [repositorio] [--apagar]
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

INDEX = "jn_versionable"
GROUPER = "jn_grouper"
PARENT_NAME = "jn_virtual_versionable_history"

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
delete = "--apagar" in sys.argv[1:]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
repository = arguments[1] if len(arguments) > 1 else "jobsnow-backup"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def count(index, query=None):
    call("POST", "/" + index + "/_refresh")
    body = None if query is None else {"query": query}
    status, answer = call("POST", "/" + index + "/_count", body)
    return answer.get("count", -1) if status == 200 else -1


def versions_in_the_groups():
    query = {"term": {"parentName": PARENT_NAME}}
    body = {"size": 0, "track_total_hits": True, "query": query, "aggs": {"versions": {"sum": {"field": "childCount"}}}}
    status, answer = call("POST", "/" + GROUPER + "/_search", body)
    if status != 200:
        return -1, -1
    groups = answer["hits"]["total"]["value"]
    versions = int(answer["aggregations"]["versions"]["value"])
    return groups, versions


def recent_snapshot():
    status, answer = call("GET", "/_snapshot/" + repository + "/_all")
    snapshots = answer.get("snapshots", []) if status == 200 else []
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    recent = [s for s in snapshots if s.get("state") == "SUCCESS" and INDEX in s.get("indices", [])
              and s.get("start_time_in_millis", 0) >= limit]
    return recent[-1]["snapshot"] if recent else ""


status, _ = call("HEAD", "/" + INDEX)
exists = status == 200
rows = count(INDEX) if exists else 0
groups, versions = versions_in_the_groups()
print(f"{INDEX}\t{'existe' if exists else 'nao existe'}\tlinhas: {rows}")
print(f"{GROUPER}\tgrupos do historico: {groups}\tversoes: {versions}")
if not exists:
    sys.exit(0)
if versions < rows:
    print("o jn_grouper tem menos versoes que o jn_versionable: rode o --gravar e o --conferir antes")
    sys.exit(1)
snapshot = recent_snapshot()
print(f"snapshot recente com {INDEX}: {snapshot or 'nenhum'}")
if not delete:
    print("nada apagado (rode com --apagar)")
    sys.exit(0)
if not snapshot:
    print(f"sem snapshot SUCCESS das ultimas 36 horas com {INDEX} em {repository}: nada apagado")
    sys.exit(1)
status, answer = call("DELETE", "/" + INDEX)
print(f"{INDEX}\tapagado: {status == 200}\t{answer.get('error', {}).get('type', '')}")
sys.exit(0 if status == 200 else 1)
