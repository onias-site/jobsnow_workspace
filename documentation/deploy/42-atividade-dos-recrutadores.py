# Datas de atividade dos recrutadores (2026-11-07), que ordenam o e-mail diario de curriculos (VisBusinessSendResumesToRecruiters):
#   lastTelegramAppearance = meia-noite do dia da mensagem mais recente do Telegram/WhatsApp com o e-mail (so ate 6 meses);
#   lastLegacyView = visualizacao mais recente no JobsNow legado (indice visualizacao_de_curriculo, que so existe no local).
# Os dois campos foram calculados no ES local por scripts\executaAtividadeDosRecrutadores.bat. Este script:
#   1. acrescenta os dois campos (long) ao mapeamento de vis_recruiter e de vis_inactive_recruiter no destino (indices
#      dynamic: strict; sem isso a escrita do registro com os campos falha);
#   2. leva os valores, por update parcial (so os dois campos), aos recrutadores do destino que estao em vis_recruiter,
#      com o mesmo _id do local (o e-mail); grava so quando o valor do destino falta ou e mais antigo (merge: producao
#      tambem escreve no indice);
#   3. deixa de fora os recrutadores com source = login (no local sao testes nossos) e nao cria recrutador: o que nao
#      estiver ativo no destino (inativo em vis_inactive_recruiter ou ausente) so e contado.
# Independe do deploy: a API e o cron antigos ignoram os campos; a ordem nova vale depois do deploy do cron.
# Idempotente. Confere o que gravou e sai com 1 se algo nao conferir.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 42-atividade-dos-recrutadores.py [destino] [origem]
import json
import os
import sys
import urllib.error
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
FIELDS = ["lastTelegramAppearance", "lastLegacyView"]
MAIN = "vis_recruiter"
TWIN = "vis_inactive_recruiter"
LOGIN = "login"
BATCH = 500


def call(base, method, path, body=None, ndjson=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if ndjson is not None:
        data = ndjson.encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method=method)
    request.add_header("Content-Type", "application/x-ndjson" if ndjson is not None else "application/json")
    if auth and base == target_url:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def scroll(base, index, query, fields):
    body = {"size": 5000, "query": query, "_source": fields}
    page = call(base, "POST", "/%s/_search?scroll=2m" % index, body)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        page = call(base, "POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})


def mget(base, index, ids):
    found = {}
    for start in range(0, len(ids), BATCH):
        docs = call(base, "POST", "/%s/_mget?_source_includes=%s" % (index, ",".join(FIELDS)), {"ids": ids[start:start + BATCH]})["docs"]
        for doc in docs:
            if doc.get("found"):
                found[doc["_id"]] = doc.get("_source", {})
    return found


print("destino:", call(target_url, "GET", "/")["cluster_name"], "| origem:", call(source_url, "GET", "/")["cluster_name"])

# 1. mapeamento
mapping = {"properties": {field: {"type": "long"} for field in FIELDS}}
for index in (MAIN, TWIN):
    result = call(target_url, "PUT", "/%s/_mapping" % index, mapping)
    print("mapeamento de %s: %s" % (index, result.get("acknowledged")))

# 2. os recrutadores do local com alguma das datas, menos os do login
with_dates = {"bool": {"should": [{"exists": {"field": field}} for field in FIELDS], "minimum_should_match": 1,
                       "must_not": [{"term": {"source": LOGIN}}]}}
local = {}
for hit in scroll(source_url, MAIN, with_dates, FIELDS + ["source"]):
    local[hit["_id"]] = {field: hit["_source"][field] for field in FIELDS if field in hit["_source"]}
logins_left_out = call(source_url, "POST", "/%s/_count" % MAIN, {"query": {"bool": {
    "should": with_dates["bool"]["should"], "minimum_should_match": 1, "filter": [{"term": {"source": LOGIN}}]}}})["count"]
print("no local: %d recrutadores com datas (%d com Telegram, %d com legado); %d do login deixados de fora" % (
    len(local), sum(1 for v in local.values() if FIELDS[0] in v), sum(1 for v in local.values() if FIELDS[1] in v), logins_left_out))

ids = sorted(local)
active = mget(target_url, MAIN, ids)
missing_ids = [i for i in ids if i not in active]
inactive = mget(target_url, TWIN, missing_ids)
absent = [i for i in missing_ids if i not in inactive]
print("no destino: %d ativos, %d inativos (nao alterados), %d ausentes (nao criados)" % (len(active), len(inactive), len(absent)))

lines = []
for record_id in sorted(active):
    stored = active[record_id]
    changes = {field: value for field, value in local[record_id].items() if stored.get(field, 0) < value}
    if not changes:
        continue
    lines.append(json.dumps({"update": {"_index": MAIN, "_id": record_id}}))
    lines.append(json.dumps({"doc": changes}))
updates = len(lines) // 2
errors = 0
for start in range(0, len(lines), 2 * BATCH):
    chunk = "\n".join(lines[start:start + 2 * BATCH]) + "\n"
    result = call(target_url, "POST", "/_bulk?refresh=true", ndjson=chunk)
    for item in result["items"]:
        if item["update"].get("error"):
            errors += 1
            print("erro:", item["update"]["_id"], item["update"]["error"].get("reason"))
print("atualizados: %d, erros: %d" % (updates, errors))

# 3. conferencia
check = mget(target_url, MAIN, sorted(active))
different = [i for i in check if any(check[i].get(f, 0) < local[i].get(f, 0) for f in FIELDS)]
print("conferencia: %d ativos com valor abaixo do local" % len(different))
for record_id in different[:10]:
    print("  ", record_id, check[record_id], local[record_id])
if errors or different:
    raise SystemExit(1)
