"""Fase 8 do plano de migracao: varre jn_grouper atras de LINUX EMBARCADO em child e parentJson, que nao sao pesquisaveis.

Uso: python 12-varrer-skills-excluidas.py <url do Elasticsearch>
A credencial vem da variavel ES_DESTINO_AUTH. Somente leitura. O esperado e zero.
"""
import json
import os
import sys
import urllib.request

TERM = "LINUX EMBARCADO"
base = sys.argv[1].rstrip("/")
auth = os.environ.get("ES_DESTINO_AUTH")


def call(method, path, body):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(base + path, data=json.dumps(body).encode("utf-8"), method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


result = call("POST", "/jn_grouper/_search?scroll=5m&size=2000", {"sort": ["_doc"], "_source": ["child", "parentJson", "parentName"]})
read = 0
found = {}
while result["hits"]["hits"]:
    for hit in result["hits"]["hits"]:
        read += 1
        text = json.dumps(hit["_source"], ensure_ascii=False)
        if TERM in text:
            name = hit["_source"].get("parentName")
            found[name] = found.get(name, 0) + 1
    result = call("POST", "/_search/scroll", {"scroll": "5m", "scroll_id": result["_scroll_id"]})
call("DELETE", "/_search/scroll", {"scroll_id": result["_scroll_id"]})
print("jn_grouper: lidos %d, com %s: %d %s" % (read, TERM, sum(found.values()), found), flush=True)
