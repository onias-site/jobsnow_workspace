# Tela Curiosidades (2026-11-14): GET /statistics/curiosities (API vis, VisServiceResumeStatistics.GetCuriosities) le, num
# so multiget por id no jn_grouper e no jn_inactive_grouper, os grupos que cada centro de custo descreve para a tela
# (JnBusinessGetGrouperCharts). Os provedores ficam numa entidade nova de configuracao do jn, semeada pela vis e pela js
# (vis e js nao se importam). Este script:
#   1. cria o indice jn_grouper_charts_providers (JnEntityGrouperChartsProviders, regra igual) com o mapeamento do local;
#   2. grava o registro da tela curiosities com os 2 provedores (VisBusinessCuriositiesCharts e
#      JsBusinessCuriositiesCharts), com o mesmo _id do local;
#   3. recalcula do zero o grupo das skills evitadas: parentName vis_virtual_avoided_skills_counter, parentJson
#      {"counter": "excludedSkills"}, childName vis_resume, child {"<skill>": curriculos ativos que a excluem};
#   4. recalcula do zero o grupo dos chamados por tipo: parentName js_virtual_contact_us_type_counter, parentJson
#      {"counter": "type"}, childName js_contact_us, child {"<tipo>": n}, contando os abertos (js_contact_us) e os ja
#      respondidos (js_contact_us_solved): o contador e um historico, todo chamado aberto conta.
# Roda DEPOIS do deploy da vis e da js (antes dele, um curriculo ou chamado gravado pela API antiga nao seria contado).
# Idempotente: cria o indice so se faltar e sobrescreve o registro e os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 76-tela-curiosidades.py
#      ou: ES_DESTINO_AUTH=<valor> python 76-tela-curiosidades.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PROVIDERS_INDEX = "jn_grouper_charts_providers"
PROVIDERS_MAPPING = {
    "mappings": {
        "dynamic": "strict",
        "properties": {"screen": {"type": "keyword"}, "providers": {"type": "keyword"}},
    }
}
SCREEN = "curiosities"
PROVIDERS = [
    "com.vis.business.statistics.VisBusinessCuriositiesCharts",
    "com.js.business.grouper.JsBusinessCuriositiesCharts",
]

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
    if status == 404:
        return
    if status != 200:
        print("falha ao ler", index, status)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "10m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def write_group(parent_name, parent_json, child_name, counts):
    parent_id = ccp_id(parent_json)
    group_id = ccp_id({"parentId": parent_id, "parentName": parent_name, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    if not counts:
        call("DELETE", path)
        print(parent_name, "sem registros: grupo apagado")
        return 0
    ordered = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
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
        return 1
    print("RELATORIO", parent_name, f"({len(ordered)} chaves, as 10 maiores)")
    for key, count in list(ordered.items())[:10]:
        print(f"{key}\t{count}")
    return 0


failures = 0

# 1. o indice dos provedores
status, _ = call("HEAD", "/" + PROVIDERS_INDEX)
if status == 404:
    status, answer = call("PUT", "/" + PROVIDERS_INDEX, PROVIDERS_MAPPING)
    if status != 200:
        print("falha ao criar", PROVIDERS_INDEX, status, answer.get("error", {}).get("type"))
        sys.exit(1)
    print(PROVIDERS_INDEX, "criado")
else:
    print(PROVIDERS_INDEX, "ja existia")

# 2. o registro da tela
record_id = ccp_id({"screen": SCREEN})
path = "/" + PROVIDERS_INDEX + "/_doc/" + urllib.parse.quote(record_id, safe="")
status, answer = call("PUT", path + "?refresh=true", {"screen": SCREEN, "providers": PROVIDERS})
if status not in (200, 201):
    failures += 1
    print("falha ao gravar o registro da tela", status, answer.get("error", {}).get("type"))
status, stored = call("GET", path)
stored_providers = stored.get("_source", {}).get("providers", [])
print("provedores da tela", SCREEN + ":", len(stored_providers), "ok" if sorted(stored_providers) == sorted(PROVIDERS) else "DIFERENTE")

# 3. as skills evitadas (so os curriculos ativos)
avoided = {}
resumes = 0
for hit in scroll("vis_resume", {"size": 500, "_source": ["skill"]}):
    resumes += 1
    excluded = {
        skill.get("skill")
        for skill in hit["_source"].get("skill", [])
        if skill.get("category") == "excludedSkills" and skill.get("skill")
    }
    for skill in excluded:
        avoided[skill] = avoided.get(skill, 0) + 1
print("vis_resume:", resumes, "curriculos ativos")
failures += write_group("vis_virtual_avoided_skills_counter", {"counter": "excludedSkills"}, "vis_resume", avoided)

# 4. os chamados por tipo (abertos e respondidos)
types = {}
for index in ("js_contact_us", "js_contact_us_solved"):
    tickets = 0
    for hit in scroll(index, {"size": 500, "_source": ["type"]}):
        ticket_type = hit["_source"].get("type")
        if not ticket_type:
            continue
        tickets += 1
        types[ticket_type] = types.get(ticket_type, 0) + 1
    print(index + ":", tickets, "chamados")
failures += write_group("js_virtual_contact_us_type_counter", {"counter": "type"}, "js_contact_us", types)

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
