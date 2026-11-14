# Insercoes das respostas do questionario de cadastro por dia e por mes (2026-11-14): js_login_answers
# (JsEntityLoginAnswers) ganhou o campo insertionDate (dd/MM/yyyy HH:mm:ss, mantido pelo decorator de
# @CcpEntityInsertionDate, JnInsertionDateEntity) e dois contadores em jn_grouper (@CcpEntityGrouperChildCounter com
# JnGrouperChildCurrentCounterEntityBeforeWrite), childName js_login_answers, parentJson {"counter": "insertionDate"}:
#   - parentName js_virtual_insertion_day_counter, child {"yyyyMMdd": n} (JnInsertionDayCounterKeys);
#   - parentName js_virtual_insertion_month_counter, child {"yyyyMM": n} (JnInsertionYearMonthCounterKeys).
# Duas fases:
#   --so-mapeamento  ANTES do deploy da js: acrescenta insertionDate (keyword) ao mapeamento de js_login_answers. O
#                    indice e dynamic strict: sem isso, a API nova falharia ao gravar uma resposta.
#   (sem opcao)      DEPOIS do deploy da js: repete o mapeamento (idempotente), preenche insertionDate nas respostas que
#                    nao o tem com o momento da versao mais antiga em jn_versionable (sem versao nenhuma, o momento
#                    atual, contado a parte) e recalcula do zero os 2 grupos.
# Idempotente: nao mexe em insertionDate ja gravado e sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script "75-insercoes-das-respostas-do-login.py --so-mapeamento"
#      powershell -File com-tunel-de-producao.ps1 -Script 75-insercoes-das-respostas-do-login.py
#      ou: ES_DESTINO_AUTH=<valor> python 75-insercoes-das-respostas-do-login.py [--so-mapeamento] [destino]
# Imprime so contagens, sem dados pessoais.
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

INDEX = "js_login_answers"
KEY_FIELDS = ["email"]
FIELD = "insertionDate"
# parentName -> funcao que tira a chave do contador de insertionDate (dd/MM/yyyy HH:mm:ss)
COUNTERS = {
    "js_virtual_insertion_day_counter": lambda date: date[6:10] + date[3:5] + date[0:2],
    "js_virtual_insertion_month_counter": lambda date: date[6:10] + date[3:5],
}
BRAZIL = datetime.timezone(datetime.timedelta(hours=-3))  # America/Sao_Paulo, sem horario de verao desde 2019

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
only_mapping = "--so-mapeamento" in sys.argv[1:]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
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


def to_text(timestamp_millis):
    moment = datetime.datetime.fromtimestamp(timestamp_millis / 1000, BRAZIL)
    return moment.strftime("%d/%m/%Y %H:%M:%S")


def key_of(values):
    return tuple(str(values.get(name)) for name in KEY_FIELDS)


# 1. mapeamento
status, answer = call("PUT", "/" + INDEX + "/_mapping", {"properties": {FIELD: {"type": "keyword"}}})
if status != 200:
    print("falha no mapeamento de", INDEX, status, answer.get("error", {}).get("type"))
    sys.exit(1)
print("mapeamento de", INDEX, "com insertionDate: ok")
if only_mapping:
    sys.exit(0)

# 2. a versao mais antiga de cada resposta
oldest = {}
for hit in scroll("jn_versionable", {"size": 1000, "_source": ["id", "timestamp"], "query": {"term": {"entity": INDEX}}}):
    source = hit["_source"]
    try:
        record_key = key_of(json.loads(source["id"]))
    except (ValueError, TypeError):
        continue
    timestamp = source.get("timestamp")
    if timestamp is None:
        continue
    if record_key not in oldest or timestamp < oldest[record_key]:
        oldest[record_key] = timestamp

now_text = to_text(datetime.datetime.now(BRAZIL).timestamp() * 1000)
failures = 0
total = had = from_version = without_version = 0
counts = {parent_name: {} for parent_name in COUNTERS}
# le tudo antes de gravar: as gravacoes uma a uma deixariam o scroll expirar
hits = list(scroll(INDEX, {"size": 500, "_source": KEY_FIELDS + [FIELD]}))
for hit in hits:
    total += 1
    source = hit["_source"]
    insertion_date = source.get(FIELD)
    if insertion_date:
        had += 1
    else:
        timestamp = oldest.get(key_of(source))
        insertion_date = to_text(timestamp) if timestamp is not None else now_text
        if timestamp is None:
            without_version += 1
        else:
            from_version += 1
        path = "/" + INDEX + "/_update/" + urllib.parse.quote(hit["_id"], safe="")
        status, answer = call("POST", path, {"doc": {FIELD: insertion_date}})
        if status != 200:
            failures += 1
            print("falha ao gravar insertionDate", status, answer.get("error", {}).get("type"))
            continue
    for parent_name, key_from in COUNTERS.items():
        key = key_from(insertion_date)
        counts[parent_name][key] = counts[parent_name].get(key, 0) + 1
print("indice\tregistros\tja tinham\tda versao\tsem versao (agora)")
print(f"{INDEX}\t{total}\t{had}\t{from_version}\t{without_version}")

# 3. os grupos
parent_json = {"counter": FIELD}
for parent_name in COUNTERS:
    parent_id = ccp_id(parent_json)
    group_id = ccp_id({"parentId": parent_id, "parentName": parent_name, "childName": INDEX})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    values = counts[parent_name]
    if not values:
        call("DELETE", path)
        print(parent_name, "sem registros: grupo apagado")
        continue
    ordered = dict(sorted(values.items()))
    group = {
        "parentId": parent_id,
        "parentName": parent_name,
        "childName": INDEX,
        "parentJson": parent_json,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar o grupo", parent_name, status, answer.get("error", {}).get("type"))
        continue
    recent = list(ordered.items())[-12:]
    print("RELATORIO", parent_name, f"({len(ordered)} chaves, as 12 mais recentes)")
    for key, count in recent:
        print(f"{key}\t{count}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
