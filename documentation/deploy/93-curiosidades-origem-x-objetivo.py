# Tela Curiosidades (2026-11-17): o contador novo do jn_grouper da origem cruzada com o objetivo do usuario, que so conta
# o que for gravado depois do deploy da js. Este script calcula do zero o que ja existe em producao: parentName
# js_virtual_login_channel_goal_counter, parentJson {"counter": "channelGoal"}, childName js_login_answers, child
# {"<channel>|<goal>": n} (as respostas do cadastro).
# O contador e virtual: nao ha indice novo, so o grupo do jn_grouper.
# Roda DEPOIS do deploy da js e dos consumidores (antes dele, uma resposta gravada pelo codigo antigo nao entraria na
# conta). Idempotente: sobrescreve o grupo.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 93-curiosidades-origem-x-objetivo.py
#      ou: ES_DESTINO_AUTH=<valor> python 93-curiosidades-origem-x-objetivo.py [destino]
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

channel_goals = {}
answers = 0
for hit in scroll("js_login_answers", {"size": 500, "_source": ["channel", "goal"]}):
    source = hit["_source"]
    channel = source.get("channel")
    goal = source.get("goal")
    if not channel or not goal:
        continue
    answers += 1
    key = channel + "|" + goal
    channel_goals[key] = channel_goals.get(key, 0) + 1
print("js_login_answers:", answers, "respostas com origem e objetivo")
failures += write_group("js_virtual_login_channel_goal_counter", {"counter": "channelGoal"}, "js_login_answers", channel_goals)

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
