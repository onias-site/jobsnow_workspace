# Apaga de producao os jn_login_email e js_login_answers sem js_login_token (pedido do usuario em 2026-11-26).
# Motivo: a tela "Ver todos" do e-mail de curriculos gravava, ao abrir, o e-mail de login e as respostas do
# pre-cadastro do destinatario (goal recruiting, channel others); os robos que leem e-mails e abrem os links a abriam
# sem que o recrutador clicasse. Desde 2026-11-26 a tela pede confirmacao antes de gravar (front).
# Criterio: o e-mail (SHA-1, como gravado) nao esta em js_login_token nem na gemea js_login_token_locked (o token ja foi
# pedido) e nao esta em js_login_password nem em js_login_password_locked (quem tem senha e usuario de verdade, mesmo com
# o token ja expirado: esses ficam).
# O que acompanha cada js_login_answers apagado, no jn_grouper:
#   - os 5 contadores do estado atual (dia e mes de insercao, goal, channel, channel|goal): cada chave e descontada;
#     chave que chega a 0 sai do child, grupo sem chave e apagado (como JnGrouperChildCurrentCounterEntityBeforeWrite);
#   - o historico versionavel (parentName jn_virtual_versionable_history, childName js_login_answers) do registro,
#     apagado como faz o expurgo do deleteAnyWhere (JnVersionablePurgeEntity).
# jn_login_email nao tem grupos. Os recrutadores que as respostas criaram ou reativaram em vis_recruiter ficam.
# Apaga por _id direto nos indices, sem os decorators. Antes de apagar: exige snapshot SUCCESS das ultimas 36 h com os
# indices tocados e grava o _source de tudo num JSONL local (fora do repositorio: tem hashes de e-mail), para restaurar.
# Sem "gravar" so conta. Idempotente. Imprime so contagens. O cache das entidades dura 1 h.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 126-login-gravado-por-robo-de-email.py -Argumentos "<copia.jsonl>,gravar"
#      local: python 126-...py <copia.jsonl> [gravar] http://127.0.0.1:9200
import datetime, json, os, sys, urllib.error, urllib.request

arguments = sys.argv[1:]
copy_path = arguments[0]
write = "gravar" in arguments[1:]
urls = [argument for argument in arguments[1:] if argument.startswith("http")]
target_url = urls[0].rstrip("/") if urls else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

GROUPER = "jn_grouper"
ANSWERS = "js_login_answers"
EMAILS = "jn_login_email"
KEPT_BY = ("js_login_token", "js_login_token_locked", "js_login_password", "js_login_password_locked")
HISTORY = "jn_virtual_versionable_history"


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


def scroll(index, query):
    status, page = call("POST", "/" + index + "/_search?scroll=10m&seq_no_primary_term=true", {"size": 1000, "query": query})
    if status == 404:
        return
    if status != 200:
        sys.exit("falha ao ler %s: %s" % (index, status))
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "10m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def emails_of(index):
    return {hit["_source"].get("email") for hit in scroll(index, {"match_all": {}})}


def keys_of(answers):
    # as chaves que os contadores dao ao registro como gravado (insertionDate dd/MM/yyyy HH:mm:ss)
    date = str(answers.get("insertionDate", ""))
    channel, goal = answers.get("channel"), answers.get("goal")
    keys = {"js_virtual_login_goal_counter": goal, "js_virtual_login_channel_counter": channel,
            "js_virtual_login_channel_goal_counter": "%s|%s" % (channel, goal)}
    if len(date) >= 10:
        keys["js_virtual_insertion_day_counter"] = date[6:10] + date[3:5] + date[0:2]
        keys["js_virtual_insertion_month_counter"] = date[6:10] + date[3:5]
    return keys


kept = set()
for index in KEPT_BY:
    kept |= emails_of(index)
email_targets = [hit for hit in scroll(EMAILS, {"match_all": {}}) if hit["_source"].get("email") not in kept]
answer_targets = [hit for hit in scroll(ANSWERS, {"match_all": {}}) if hit["_source"].get("email") not in kept]
target_hashes = {hit["_source"]["email"] for hit in answer_targets}

history_targets = []
for hit in scroll(GROUPER, {"bool": {"filter": [{"term": {"parentName": HISTORY}}, {"term": {"childName": ANSWERS}}]}}):
    parent = hit["_source"].get("parentJson") or {}
    parent = json.loads(parent) if isinstance(parent, str) else parent
    if (parent.get("primaryKey") or {}).get("email") in target_hashes:
        history_targets.append(hit)

deltas = {}
for hit in answer_targets:
    for parent_name, key in keys_of(hit["_source"]).items():
        deltas.setdefault(parent_name, {})
        deltas[parent_name][key] = deltas[parent_name].get(key, 0) + 1

counter_writes = []
for parent_name, keys in deltas.items():
    groups = list(scroll(GROUPER, {"bool": {"filter": [{"term": {"parentName": parent_name}}, {"term": {"childName": ANSWERS}}]}}))
    for group in groups:
        counters = json.loads((group["_source"].get("child") or ["{}"])[0])
        before = sum(counters.values())
        for key, amount in keys.items():
            left = int(counters.get(key, 0)) - amount
            if left > 0:
                counters[key] = left
                continue
            counters.pop(key, None)
        counter_writes.append((group, counters))
        print(parent_name, before, "->", sum(counters.values()))

print("jn_login_email a apagar:", len(email_targets), "| js_login_answers a apagar:", len(answer_targets),
      "| historicos a apagar:", len(history_targets), "| contadores a corrigir:", len(counter_writes))
by_kind = {}
for hit in answer_targets:
    source = hit["_source"]
    kind = (str(source.get("insertionDate", ""))[:10], source.get("goal"), source.get("channel"))
    by_kind[kind] = by_kind.get(kind, 0) + 1
for kind in sorted(by_kind, key=lambda item: (item[0][6:10] + item[0][3:5] + item[0][0:2], item[1], item[2])):
    print("  respostas", kind, by_kind[kind])
if not write:
    print("simulacao: nada apagado (passe 'gravar')")
    sys.exit(0)

if "9210" in target_url:
    status, answer = call("GET", "/_snapshot/jobsnow-backup/_all")
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    needed = {EMAILS, ANSWERS, GROUPER}
    recent = [s for s in answer.get("snapshots", []) if s.get("state") == "SUCCESS"
              and needed <= set(s.get("indices", [])) and s.get("start_time_in_millis", 0) >= limit]
    print("snapshot recente:", recent[-1]["snapshot"] if recent else "nenhum")
    if not recent:
        sys.exit("sem snapshot das ultimas 36 h: nada apagado")

with open(copy_path, "a", encoding="utf-8") as copy:
    for hit in email_targets + answer_targets + history_targets:
        copy.write(json.dumps({"index": hit["_index"], "_id": hit["_id"], "_source": hit["_source"]}, ensure_ascii=False) + "\n")
    for group, _ in counter_writes:
        copy.write(json.dumps({"index": GROUPER, "_id": group["_id"], "_source": group["_source"]}, ensure_ascii=False) + "\n")
print("copia gravada antes do delete")

failures = 0
for group, counters in counter_writes:
    path = "/%s/_doc/%s?if_seq_no=%s&if_primary_term=%s" % (GROUPER, group["_id"], group["_seq_no"], group["_primary_term"])
    if not counters:
        status, _ = call("DELETE", path)
    else:
        source = dict(group["_source"])
        source["child"] = [json.dumps(counters, separators=(",", ":"))]
        source["childCount"] = len(counters)
        status, _ = call("PUT", path, source)
    if status not in (200, 201):
        failures += 1
        print("falha no contador", group["_source"]["parentName"], status)

deleted = 0
targets = email_targets + answer_targets + history_targets
for start in range(0, len(targets), 1000):
    lines = [json.dumps({"delete": {"_index": hit["_index"], "_id": hit["_id"]}}) for hit in targets[start:start + 1000]]
    request = urllib.request.Request(target_url + "/_bulk", data=("\n".join(lines) + "\n").encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/x-ndjson")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request) as response:
        answer = json.loads(response.read())
    for item in answer["items"]:
        result = item["delete"]
        if result.get("result") == "deleted":
            deleted += 1
        elif result.get("status") != 404:
            failures += 1
call("POST", "/%s,%s,%s/_refresh" % (EMAILS, ANSWERS, GROUPER))
for index in (EMAILS, ANSWERS):
    status, answer = call("GET", "/" + index + "/_count")
    print(index, "restam:", answer.get("count"))
print("apagados:", deleted, "| falhas:", failures)
sys.exit(1 if failures else 0)
