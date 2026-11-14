# Contador por dia de insercao (2026-11-14): o curriculo (vis_resume) e a visualizacao de curriculo (vis_viewed_resume)
# ganharam, ao lado do contador por mes (script 61), um contador por dia em jn_grouper (@CcpEntityGrouperChildCounter
# com JnGrouperChildCurrentCounterEntityBeforeWrite e JnInsertionDayCounterKeys): um grupo por entidade (parentName
# vis_virtual_insertion_day_counter, parentJson {"counter": "insertionDate"}, childName vis_resume ou
# vis_viewed_resume) cujo unico child e o texto JSON {"yyyyMMdd": <quantos registros ativos inseridos naquele dia>}.
# E o grafico de linhas da tela Oferta X Demanda (GET /statistics/resumes/totals, item byDay).
# Este script recalcula do zero os 2 grupos a partir do insertionDate ja gravado (preenchido pelo script 61); so a ponta
# principal conta (os curriculos inativos ficam fora). Um registro sem insertionDate e contado a parte e fica fora.
# Roda DEPOIS do deploy da vis e dos consumidores. Idempotente: sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 73-contador-por-dia-de-insercao.py
#      ou: ES_DESTINO_AUTH=<valor> python 73-contador-por-dia-de-insercao.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_insertion_day_counter"
FIELD = "insertionDate"
CHILD_NAMES = ("vis_resume", "vis_viewed_resume")

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


def day_of(insertion_date):
    # dd/MM/yyyy HH:mm:ss -> yyyyMMdd
    return insertion_date[6:10] + insertion_date[3:5] + insertion_date[0:2]


failures = 0
parent_json = {"counter": FIELD}
parent_id = ccp_id(parent_json)
print("indice\tregistros\tsem insertionDate\tdias")
for child_name in CHILD_NAMES:
    days = {}
    total = without_date = 0
    for hit in scroll(child_name, {"size": 1000, "_source": [FIELD]}):
        total += 1
        insertion_date = hit["_source"].get(FIELD)
        if not insertion_date:
            without_date += 1
            continue
        day = day_of(insertion_date)
        days[day] = days.get(day, 0) + 1
    print(f"{child_name}\t{total}\t{without_date}\t{len(days)}")

    group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    if not days:
        call("DELETE", path)
        print(child_name, "sem registros: grupo apagado")
        continue
    ordered = dict(sorted(days.items()))
    group = {
        "parentId": parent_id,
        "parentName": PARENT_NAME,
        "childName": child_name,
        "parentJson": parent_json,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar o grupo de", child_name, status, answer.get("error", {}).get("type"))
        continue
    recent = list(ordered.items())[-10:]
    print("RELATORIO", child_name, "(ativos por dia de insercao, os 10 dias mais recentes)")
    for day, count in recent:
        print(f"{day}\t{count}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
