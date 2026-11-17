# Tela Curiosidades (2026-11-17): os chamados do vis entram no grafico de chamados, ao lado dos do fale conosco, com os
# tipos do combo da tela de chamados do usuario (Meus dados > Chamados). Contadores novos do jn_grouper, um historico
# (todo chamado ja aberto conta, o pendente e o encerrado), que so contam o que for gravado depois do deploy da vis. Este
# script calcula do zero o que ja existe em producao, um grupo por entidade, parentName vis_virtual_ticket_kind_counter,
# parentJson {"counter": "ticketKind"}:
#   childName vis_skill_fix_hierarchy_pending: {"hierarchyAdd": n, "hierarchyRemove": n}, pelo type, contando a
#      pendente e a vis_skill_fix_hierarchy_fulfiled;
#   childName vis_skill_pending: {"skillSuggestion": n}, contando a pendente, a vis_skill_approved e a vis_skill_rejected;
#   childName vis_invalid_linkedin_report: {"invalidLinkedin": n}, contando a principal e a vis_invalid_linkedin_report_solved.
# Os contadores sao virtuais: nao ha indice novo, so os 3 grupos do jn_grouper.
# Roda DEPOIS do deploy da vis e dos consumidores (antes dele, um chamado gravado pelo codigo antigo nao entraria na
# conta). Idempotente: sobrescreve os 3 grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 94-curiosidades-chamados-do-vis.py
#      ou: ES_DESTINO_AUTH=<valor> python 94-curiosidades-chamados-do-vis.py [destino]
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
        call("DELETE", path + "?refresh=true")
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
    status, stored = call("GET", path)
    stored_child = stored.get("_source", {}).get("child", [""])[0]
    same = json.loads(stored_child or "{}") == ordered
    print("RELATORIO", parent_name, f"({len(ordered)} chaves, conferido: {'ok' if same else 'DIFERENTE'})")
    for key, count in ordered.items():
        print(f"{key}\t{count}")
    return 0 if same else 1


failures = 0
PARENT_NAME = "vis_virtual_ticket_kind_counter"
PARENT_JSON = {"counter": "ticketKind"}
HIERARCHY_KINDS = {"add": "hierarchyAdd", "remove": "hierarchyRemove"}


def count_records(indexes, key_of):
    counts = {}
    for index in indexes:
        total = 0
        for hit in scroll(index, {"size": 500, "_source": ["type"]}):
            key = key_of(hit["_source"])
            if not key:
                continue
            total += 1
            counts[key] = counts.get(key, 0) + 1
        print(index + ":", total, "chamados")
    return counts


hierarchy = count_records(["vis_skill_fix_hierarchy_pending", "vis_skill_fix_hierarchy_fulfiled"], lambda source: HIERARCHY_KINDS.get(source.get("type")))
failures += write_group(PARENT_NAME, PARENT_JSON, "vis_skill_fix_hierarchy_pending", hierarchy)

skills = count_records(["vis_skill_pending", "vis_skill_approved", "vis_skill_rejected"], lambda source: "skillSuggestion")
failures += write_group(PARENT_NAME, PARENT_JSON, "vis_skill_pending", skills)

linkedin = count_records(["vis_invalid_linkedin_report", "vis_invalid_linkedin_report_solved"], lambda source: "invalidLinkedin")
failures += write_group(PARENT_NAME, PARENT_JSON, "vis_invalid_linkedin_report", linkedin)

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
