# Recrutadores ativos no JobsNow legado (2026-11-15), o 5o grupo da ordem do e-mail diario de curriculos
# (VisBusinessSendResumesToRecruiters, vis 2b41802): 1) viu nos ultimos 35 dias; 2) cadastro aguardando o 1o e-mail;
# 3) Telegram (183 dias); 4) visualizou no legado; 5) ativo no legado (legacyActive, fila propria em rodizio pelo SHA-1);
# 6) dominio nao profissional; 7) fila de quem nunca viu.
# Ativo no legado = status 1 no indice recruiters ou old_recruiters do ES 7.4 local (porta 9201; e o que o
# RecruitersService do legado chama de ativo). O e-mail e o campo id do documento, normalizado como no
# VisBusinessPrepareRecruiter (sem acento, minusculo, sem espacos nas pontas). Este script:
#   1. acrescenta legacyActive (boolean) ao mapeamento de vis_recruiter e de vis_inactive_recruiter no destino (indices
#      dynamic: strict);
#   2. grava legacyActive = true, por update parcial (so esse campo), nos recrutadores do destino em vis_recruiter cujo
#      e-mail e ativo no legado; nao cria recrutador nem mexe nos inativos (merge: producao tambem escreve no indice).
# O _id de vis_recruiter e calculado pelo codigo (AEI), entao o script acha o documento pelo campo email.
# Independe do deploy (a API e o cron antigos ignoram o campo); a ordem nova vale depois do deploy do cron.
# Idempotente. Confere o que gravou e sai com 1 se algo nao conferir. Imprime so contagens.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 86-recrutadores-ativos-no-legado.py
#      ou: ES_DESTINO_AUTH=<valor> python 86-recrutadores-ativos-no-legado.py [destino] [legado]
#      local: python 86-recrutadores-ativos-no-legado.py http://127.0.0.1:9200
import json
import os
import sys
import unicodedata
import urllib.error
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
legacy_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9201"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
FIELD = "legacyActive"
MAIN = "vis_recruiter"
TWIN = "vis_inactive_recruiter"
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
    try:
        with opener.open(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        print("falha", method, path, error.code, error.read().decode("utf-8")[:300])
        sys.exit(1)


def scroll(base, index, query, fields):
    page = call(base, "POST", "/%s/_search?scroll=2m" % index, {"size": 5000, "query": query, "_source": fields})
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        page = call(base, "POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call(base, "DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def normalize(text):
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).strip().lower()


legacy_active = set()
for index, query in (("recruiters", {"term": {"status": 1}}), ("old_recruiters", {"term": {"status.keyword": "1"}})):
    found = 0
    for hit in scroll(legacy_url, index, query, ["id"]):
        legacy_active.add(normalize(hit["_source"].get("id") or hit["_id"]))
        found += 1
    print("ativos no legado em", index, found)
print("e-mails distintos ativos no legado:", len(legacy_active))
if not legacy_active:
    print("nenhum ativo no legado: o ES 7.4 esta no ar?")
    sys.exit(1)

for index in (MAIN, TWIN):
    call(target_url, "PUT", "/%s/_mapping" % index, {"properties": {FIELD: {"type": "boolean"}}})
    print("mapeamento de", FIELD, "em", index, "ok")

to_update = []
already = 0
for hit in scroll(target_url, MAIN, {"match_all": {}}, ["email", FIELD]):
    source = hit["_source"]
    email = source.get("email", "")
    if email not in legacy_active:
        continue
    if source.get(FIELD) is True:
        already += 1
        continue
    to_update.append(hit["_id"])
print("ja marcados:", already, "| a marcar:", len(to_update))

for start in range(0, len(to_update), BATCH):
    lines = []
    for doc_id in to_update[start:start + BATCH]:
        lines.append(json.dumps({"update": {"_index": MAIN, "_id": doc_id}}))
        lines.append(json.dumps({"doc": {FIELD: True}}))
    answer = call(target_url, "POST", "/_bulk", ndjson="\n".join(lines) + "\n")
    if answer.get("errors"):
        failures = [item["update"].get("error") for item in answer["items"] if item["update"].get("error")]
        print("falhas no bulk:", len(failures), failures[:2])
        sys.exit(1)

call(target_url, "POST", "/%s/_refresh" % MAIN)
marked = call(target_url, "POST", "/%s/_count" % MAIN, {"query": {"term": {FIELD: True}}})["count"]
expected = already + len(to_update)
print("marcados com", FIELD, "no destino:", marked, "| esperados:", expected)
if marked < expected:
    sys.exit(1)
print("ok")
