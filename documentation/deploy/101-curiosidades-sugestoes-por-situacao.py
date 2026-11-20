# Tres graficos novos na tela Curiosidades (2026-11-20): as sugestoes do candidato por situacao (pending, approved,
# rejected), contadores em jn_grouper com parentName vis_virtual_suggestion_status_counter:
#   - Sugestoes de novas habilidades: parentJson {"counter": "skillSuggestion"}, childName vis_skill_pending,
#     child {"pending": vis_skill_pending, "approved": vis_skill_approved, "rejected": vis_skill_rejected}.
#   - Sugestoes de associacao / desassociacao de hierarquia: parentJson {"counter": "add"} / {"counter": "remove"},
#     childName vis_skill_fix_hierarchy_item_pending, child {"pending": vis_skill_fix_hierarchy_item_pending,
#     "approved": vis_skill_fix_hierarchy_item_approved, "rejected": vis_skill_fix_hierarchy_item_rejected (a gemea)},
#     cada indice contado pelo campo type do item.
# Os contadores sao corrigidos pelos side effects das escritas e das transferencias (VisSuggestionStatusCounters); este
# script recalcula do zero os 3 grupos a partir dos registros ja gravados. Roda DEPOIS do deploy da vis e dos
# consumidores (antes dele, uma escrita feita pelo codigo antigo nao seria contada). Idempotente: sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 101-curiosidades-sugestoes-por-situacao.py
#      ou: ES_DESTINO_AUTH=<valor> python 101-curiosidades-sugestoes-por-situacao.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


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


def count_records(index):
    status, answer = call("GET", "/" + index + "/_count")
    if status == 404:
        print(index, "inexistente: 0")
        return 0
    if status != 200:
        print("falha ao contar", index, status)
        sys.exit(1)
    print(index, "registros:", answer["count"])
    return answer["count"]


def count_by_type(index):
    counts = {}
    status, _ = call("GET", "/" + index + "/_count")
    if status == 404:
        print(index, "inexistente: 0")
        return counts
    total = 0
    for hit in scroll(index, {"size": 2000, "_source": ["type"]}):
        total += 1
        item_type = hit["_source"].get("type")
        counts[item_type] = counts.get(item_type, 0) + 1
    print(index, "registros:", total, counts)
    return counts


def without_zeros(counts):
    return {key: value for key, value in counts.items() if value > 0}


skill_suggestions = without_zeros({
    "pending": count_records("vis_skill_pending"),
    "approved": count_records("vis_skill_approved"),
    "rejected": count_records("vis_skill_rejected"),
})
pending_items = count_by_type("vis_skill_fix_hierarchy_item_pending")
approved_items = count_by_type("vis_skill_fix_hierarchy_item_approved")
rejected_items = count_by_type("vis_skill_fix_hierarchy_item_rejected")
results = [write_group("vis_virtual_suggestion_status_counter", {"counter": "skillSuggestion"}, "vis_skill_pending", skill_suggestions)]
for item_type in ("add", "remove"):
    items = without_zeros({
        "pending": pending_items.get(item_type, 0),
        "approved": approved_items.get(item_type, 0),
        "rejected": rejected_items.get(item_type, 0),
    })
    results.append(write_group("vis_virtual_suggestion_status_counter", {"counter": item_type}, "vis_skill_fix_hierarchy_item_pending", items))
print("OK" if all(results) else "FALHAS")
print("cache das entidades: 1 h; a tela le os grupos por id (o front guarda a resposta por 1 h no navegador)")
sys.exit(0 if all(results) else 1)
