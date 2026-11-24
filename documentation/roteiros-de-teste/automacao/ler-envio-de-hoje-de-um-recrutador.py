# Le de producao, so leitura, o e-mail de curriculos que um recrutador recebeu hoje (America/Sao_Paulo): a lista gravada
# pelo envio (vis_recruiter_resumes, descartavel diario) e o assunto (jn_email_message_sent), os dois guardados em
# jn_disposable_record. O campo json desse indice nao e indexado: o filtro pelo e-mail (SHA-1) e feito aqui.
# Grava no arquivo {"vis_recruiter_resumes": {...}, "jn_email_message_sent": {...}}; imprime so contagens e o assunto.
# Uso: ES_DESTINO_AUTH=<valor> python ler-envio-de-hoje-de-um-recrutador.py <e-mail do recrutador> <arquivo de saida>
import datetime
import hashlib
import json
import os
import sys
import urllib.request

BASE = "http://127.0.0.1:9210"
AUTH = os.environ.get("ES_DESTINO_AUTH", "")
TEMPLATE = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"


def call(path, body):
    request = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST")
    request.add_header("Content-Type", "application/json")
    if AUTH:
        request.add_header("Authorization", AUTH)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def java_sha1(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


email = sys.argv[1].strip().lower()
out = sys.argv[2]
email_hash = java_sha1(email)
sao_paulo = datetime.timezone(datetime.timedelta(hours=-3))
today = datetime.datetime.now(sao_paulo).replace(hour=0, minute=0, second=0, microsecond=0)
since = int(today.timestamp() * 1000)
result = {}
for entity in ("vis_recruiter_resumes", "jn_email_message_sent"):
    found = call("/jn_disposable_record/_search", {"size": 10000, "sort": [{"trueTimestamp": "desc"}],
        "query": {"bool": {"filter": [{"term": {"entity": entity}}, {"range": {"trueTimestamp": {"gte": since}}}]}}})
    hits = [hit for hit in found["hits"]["hits"] if (hit["_source"].get("json") or {}).get("email") in (email_hash, email)]
    if entity == "jn_email_message_sent":
        hits = [hit for hit in hits if hit["_source"]["json"].get("subjectType") == TEMPLATE]
    if not hits:
        print(entity, "sem registro de hoje para este recrutador")
        sys.exit(2)
    source = hits[0]["_source"]
    when = datetime.datetime.fromtimestamp(source["trueTimestamp"] / 1000, sao_paulo)
    print(entity, "gravado em", when.strftime("%d/%m/%Y %H:%M:%S"))
    result[entity] = source["json"]
rows = result["vis_recruiter_resumes"].get("resumes") or []
print("linhas:", len(rows), "| ja visualizados:", sum(1 for row in rows if row.get("viewed")), "| nunca visualizados:", sum(1 for row in rows if not row.get("viewed")))
print("assunto:", result["jn_email_message_sent"].get("subject"))
with open(out, "w", encoding="utf-8") as file:
    json.dump(result, file, ensure_ascii=False)
