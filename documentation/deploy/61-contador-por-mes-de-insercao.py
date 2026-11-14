# Contador por mes de insercao (2026-11-12): o curriculo (vis_resume e a gemea vis_inactive_resume) e a visualizacao
# de curriculo (vis_viewed_resume) ganharam o campo insertionDate (dd/MM/yyyy HH:mm:ss, mantido pelo decorator de
# @CcpEntityInsertionDate, JnInsertionDateEntity) e um contador em jn_grouper (@CcpEntityGrouperChildCounter com
# JnGrouperChildCurrentCounterEntityBeforeWrite e JnInsertionYearMonthCounterKeys): um grupo por entidade (parentName
# vis_virtual_insertion_month_counter, parentJson {"counter": "insertionDate"}, childName vis_resume ou
# vis_viewed_resume) cujo unico child e o texto JSON {"yyyyMM": <quantos registros ativos inseridos naquele mes>}.
# Este script:
#   1. acrescenta insertionDate (keyword) ao mapeamento dos 3 indices;
#   2. preenche insertionDate nos registros que nao o tem: o momento da versao mais antiga em jn_versionable (o
#      curriculo procurado como vis_resume e vis_inactive_resume); sem versao nenhuma, o momento atual (contado a parte);
#   3. recalcula do zero os 2 grupos (so a ponta principal conta: os curriculos inativos ficam fora).
# Roda DEPOIS do deploy da vis e dos consumidores (antes dele, um curriculo salvo perderia o campo: o save substitui o
# registro). Idempotente: nao mexe em insertionDate ja gravado e sobrescreve os grupos.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 61-contador-por-mes-de-insercao.py
#      ou: ES_DESTINO_AUTH=<valor> python 61-contador-por-mes-de-insercao.py [destino]
# Imprime so contagens, sem dados pessoais.
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_insertion_month_counter"
FIELD = "insertionDate"
# indice -> (nomes da entidade em jn_versionable, campos da chave primaria, conta no grupo de qual childName)
INDICES = {
    "vis_resume": (["vis_resume", "vis_inactive_resume"], ["email"], "vis_resume"),
    "vis_inactive_resume": (["vis_resume", "vis_inactive_resume"], ["email"], None),
    "vis_viewed_resume": (["vis_viewed_resume"], ["email", "linkedin"], "vis_viewed_resume"),
}
BRAZIL = datetime.timezone(datetime.timedelta(hours=-3))  # America/Sao_Paulo, sem horario de verao desde 2019

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


def to_text(timestamp_millis):
    moment = datetime.datetime.fromtimestamp(timestamp_millis / 1000, BRAZIL)
    return moment.strftime("%d/%m/%Y %H:%M:%S")


def year_month(insertion_date):
    # dd/MM/yyyy HH:mm:ss -> yyyyMM
    return insertion_date[6:10] + insertion_date[3:5]


def key_of(values, key_fields):
    return tuple(str(values.get(name)) for name in key_fields)


failures = 0
# 1. mapeamento
for index in INDICES:
    status, answer = call("PUT", "/" + index + "/_mapping", {"properties": {FIELD: {"type": "keyword"}}})
    if status != 200:
        print("falha no mapeamento de", index, status, answer.get("error", {}).get("type"))
        sys.exit(1)
print("mapeamentos com insertionDate: ok")

# 2. a versao mais antiga de cada registro
oldest_by_entities = {}
for index, (entity_names, key_fields, _) in INDICES.items():
    names = tuple(entity_names)
    if names in oldest_by_entities:
        continue
    oldest = {}
    body = {"size": 1000, "_source": ["id", "timestamp"], "query": {"terms": {"entity": list(names)}}}
    for hit in scroll("jn_versionable", body):
        source = hit["_source"]
        try:
            record_key = key_of(json.loads(source["id"]), key_fields)
        except (ValueError, TypeError):
            continue
        timestamp = source.get("timestamp")
        if timestamp is None:
            continue
        if record_key not in oldest or timestamp < oldest[record_key]:
            oldest[record_key] = timestamp
    oldest_by_entities[names] = oldest

now_text = to_text(datetime.datetime.now(BRAZIL).timestamp() * 1000)
counters = {}
print("indice\tregistros\tja tinham\tda versao\tsem versao (agora)")
for index, (entity_names, key_fields, child_name) in INDICES.items():
    oldest = oldest_by_entities[tuple(entity_names)]
    total = had = from_version = without_version = 0
    body = {"size": 500, "_source": key_fields + [FIELD]}
    # le tudo antes de gravar: as gravacoes uma a uma deixariam o scroll expirar
    hits = list(scroll(index, body))
    for hit in hits:
        total += 1
        source = hit["_source"]
        insertion_date = source.get(FIELD)
        if insertion_date:
            had += 1
        else:
            timestamp = oldest.get(key_of(source, key_fields))
            insertion_date = to_text(timestamp) if timestamp is not None else now_text
            if timestamp is None:
                without_version += 1
            else:
                from_version += 1
            path = "/" + index + "/_update/" + urllib.parse.quote(hit["_id"], safe="")
            status, answer = call("POST", path, {"doc": {FIELD: insertion_date}})
            if status != 200:
                failures += 1
                print("falha ao gravar insertionDate em", index, status, answer.get("error", {}).get("type"))
                continue
        if child_name:
            months = counters.setdefault(child_name, {})
            month = year_month(insertion_date)
            months[month] = months.get(month, 0) + 1
    print(f"{index}\t{total}\t{had}\t{from_version}\t{without_version}")

# 3. os grupos
parent_json = {"counter": FIELD}
parent_id = ccp_id(parent_json)
for child_name in ("vis_resume", "vis_viewed_resume"):
    months = counters.get(child_name, {})
    group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    if not months:
        call("DELETE", path)
        print(child_name, "sem registros: grupo apagado")
        continue
    ordered = dict(sorted(months.items()))
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
    print("RELATORIO", child_name, "(ativos por mes de insercao)")
    for month, count in ordered.items():
        print(f"{month}\t{count}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
