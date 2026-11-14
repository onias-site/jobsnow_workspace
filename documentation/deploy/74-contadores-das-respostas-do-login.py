# Contadores das respostas do questionario de cadastro (2026-11-14): js_login_answers (JsEntityLoginAnswers) ganhou dois
# contadores em jn_grouper (@CcpEntityGrouperChildCounter com JnGrouperChildCurrentCounterEntityBeforeWrite), o estado
# atual de cada campo:
#   - parentName js_virtual_login_goal_counter, parentJson {"counter": "goal"}, child {"<goal>": n} (jobs, recruiting);
#   - parentName js_virtual_login_channel_counter, parentJson {"counter": "channel"}, child {"<channel>": n} (linkedin,
#     telegram, friends, others).
# childName js_login_answers nos dois. A entidade nao tem gemea: so o jn_grouper.
# Este script recalcula do zero os 2 grupos a partir dos registros ja gravados. Um registro sem o campo fica fora daquele
# contador (contado a parte).
# Roda DEPOIS do deploy da js e dos consumidores (antes dele, uma resposta gravada pela API antiga nao seria contada).
# Idempotente: sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 74-contadores-das-respostas-do-login.py
#      ou: ES_DESTINO_AUTH=<valor> python 74-contadores-das-respostas-do-login.py [destino]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CHILD_NAME = "js_login_answers"
# campo -> parentName do contador
COUNTERS = {
    "goal": "js_virtual_login_goal_counter",
    "channel": "js_virtual_login_channel_counter",
}

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


counts = {field: {} for field in COUNTERS}
missing = {field: 0 for field in COUNTERS}
total = 0
for hit in scroll(CHILD_NAME, {"size": 1000, "_source": list(COUNTERS)}):
    total += 1
    source = hit["_source"]
    for field in COUNTERS:
        value = source.get(field)
        if not value:
            missing[field] += 1
            continue
        counts[field][value] = counts[field].get(value, 0) + 1
print(CHILD_NAME, "registros:", total)

failures = 0
for field, parent_name in COUNTERS.items():
    parent_json = {"counter": field}
    parent_id = ccp_id(parent_json)
    group_id = ccp_id({"parentId": parent_id, "parentName": parent_name, "childName": CHILD_NAME})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    values = counts[field]
    if not values:
        call("DELETE", path)
        print(field, "sem registros: grupo apagado")
        continue
    ordered = dict(sorted(values.items()))
    group = {
        "parentId": parent_id,
        "parentName": parent_name,
        "childName": CHILD_NAME,
        "parentJson": parent_json,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar o grupo de", field, status, answer.get("error", {}).get("type"))
        continue
    print("RELATORIO", field, f"(sem o campo: {missing[field]})")
    for value, count in ordered.items():
        print(f"{value}\t{count}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
