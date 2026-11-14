# Totais por ddd (2026-11-14): o curriculo (vis_resume) e a visualizacao de curriculo (vis_viewed_resume) ganharam um
# contador em jn_grouper (@CcpEntityGrouperChildCounter com JnGrouperChildCurrentCounterEntityBeforeWrite e
# VisDddCounterKeys): um grupo por entidade (parentName vis_virtual_ddd_counter, parentJson {"counter": "ddd"},
# childName vis_resume ou vis_viewed_resume) cujo unico child e o texto JSON {"<ddd>": <quantos registros ativos listam
# aquele ddd>}. Um registro com varios ddds conta uma vez em cada. Sao os totais dos titulos das pastas da tela Oferta X
# Demanda (GET statistics/resumes/totals).
# O decorator so age nas escritas feitas depois do deploy: este script recalcula do zero os 2 grupos a partir da ponta
# principal (os curriculos inativos, em vis_inactive_resume, e as visualizacoes em vis_inactive_viewed_resume ficam fora).
# Roda DEPOIS do deploy da vis e dos consumidores (antes dele, o codigo antigo nao corrige o grupo nas escritas e o total
# envelhece). Idempotente: sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 72-totais-por-ddd-no-grouper.py
#      ou: ES_DESTINO_AUTH=<valor> python 72-totais-por-ddd-no-grouper.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_ddd_counter"
PARENT_JSON = {"counter": "ddd"}
INDICES = {"vis_resume": "vis_resume", "vis_viewed_resume": "vis_viewed_resume"}

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


failures = 0
parent_id = ccp_id(PARENT_JSON)
for index, child_name in INDICES.items():
    totals = {}
    records = without_ddd = 0
    for hit in scroll(index, {"size": 500, "_source": ["ddd"]}):
        records += 1
        ddds = hit["_source"].get("ddd") or []
        if not ddds:
            without_ddd += 1
        # cada ddd uma vez por registro, como inteiro (o ES pode devolver 11.0)
        for ddd in {int(float(value)) for value in ddds}:
            key = str(ddd)
            totals[key] = totals.get(key, 0) + 1
    group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    print(f"{index}: {records} registros, {without_ddd} sem ddd, {len(totals)} ddds")
    if not totals:
        call("DELETE", path)
        print(child_name, "sem registros: grupo apagado")
        continue
    ordered = dict(sorted(totals.items(), key=lambda item: int(item[0])))
    group = {
        "parentId": parent_id,
        "parentName": PARENT_NAME,
        "childName": child_name,
        "parentJson": PARENT_JSON,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar o grupo de", child_name, status, answer.get("error", {}).get("type"))
        continue
    print("RELATORIO", child_name, "(ddd: registros ativos)")
    for ddd, count in ordered.items():
        print(f"{ddd}\t{count}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
