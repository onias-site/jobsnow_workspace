# Dois graficos novos na tela Curiosidades (2026-11-17), dois contadores novos em jn_grouper (@CcpEntityGrouperChildCounter
# com JnGrouperChildCurrentCounterEntityBeforeWrite, o estado atual, so os registros ativos):
#   - Origem dos recrutadores: parentName vis_virtual_recruiter_source_counter, parentJson {"counter": "source"},
#     childName vis_recruiter, child {"<source>": recrutadores ativos} (legacy, telegram, login, support). A tela deixa
#     o legacy de fora; o contador guarda todos.
#   - DDDs do curriculo: parentName vis_virtual_resume_region_scope_counter, parentJson {"counter": "ddd"}, childName
#     vis_resume, child {"<alcance>": curriculos ativos}, um alcance por curriculo pelos ddds distintos
#     (VisResumeRegionScopeCounterKeys): homeOfficeOnly (o ddd 10), oneRegion (1 regiao), anyRegion (as 67 regioes
#     metropolitanas) e severalRegions (o resto).
# Este script recalcula do zero os 2 grupos a partir dos registros ja gravados (vis_recruiter e vis_resume, so o lado
# principal). Roda DEPOIS do deploy da vis e dos consumidores (antes dele, um registro gravado pelo codigo antigo nao
# seria contado). Idempotente: sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 92-curiosidades-origem-dos-recrutadores-e-ddds.py
#      ou: ES_DESTINO_AUTH=<valor> python 92-curiosidades-origem-dos-recrutadores-e-ddds.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HOME_OFFICE_DDD = 10
METROPOLITAN_REGIONS = 67

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
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


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def scroll(index, body):
    status, page = call("POST", "/" + index + "/_search?scroll=10m", body)
    if status != 200:
        print("falha ao ler", index, status)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "10m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def region_scope(ddds):
    distinct = {int(float(ddd)) for ddd in ddds}
    if not distinct:
        return None
    if HOME_OFFICE_DDD in distinct:
        return "homeOfficeOnly"
    if len(distinct) == 1:
        return "oneRegion"
    if len(distinct) >= METROPOLITAN_REGIONS:
        return "anyRegion"
    return "severalRegions"


def count(index, field, key_of):
    counts = {}
    total = 0
    without = 0
    for hit in scroll(index, {"size": 2000, "_source": [field]}):
        total += 1
        value = hit["_source"].get(field)
        key = key_of(value) if value else None
        if not key:
            without += 1
            continue
        counts[key] = counts.get(key, 0) + 1
    print(index, "registros:", total, f"(sem {field}: {without})")
    return counts


def write_group(parent_name, parent_json, child_name, counts):
    parent_id = ccp_id(parent_json)
    group_id = ccp_id({"parentId": parent_id, "parentName": parent_name, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    if not counts:
        call("DELETE", path)
        print(parent_name, "sem registros: grupo apagado")
        return True
    ordered = dict(sorted(counts.items()))
    group = {
        "parentId": parent_id,
        "parentName": parent_name,
        "childName": child_name,
        "parentJson": parent_json,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        print("falha ao gravar o grupo", parent_name, status, answer.get("error", {}).get("type"))
        return False
    print("RELATORIO", parent_name)
    for key, value in ordered.items():
        print(f"{key}\t{value}")
    return True


sources = count("vis_recruiter", "source", lambda value: value)
scopes = count("vis_resume", "ddd", region_scope)
results = [
    write_group("vis_virtual_recruiter_source_counter", {"counter": "source"}, "vis_recruiter", sources),
    write_group("vis_virtual_resume_region_scope_counter", {"counter": "ddd"}, "vis_resume", scopes),
]
print("OK" if all(results) else "FALHAS")
print("cache das entidades: 1 h; a tela le os grupos por id (o front guarda a resposta por 1 h no navegador)")
sys.exit(0 if all(results) else 1)
