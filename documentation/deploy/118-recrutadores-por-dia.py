# Recrutadores por dia: grava em jn_system_parameter o parametro
#   com.vis.business.recruiter.resumes.VisRecruiterResumesSystemParameters.recruitersPerDay
# que diz quantos recrutadores recebem por dia o e-mail dos curriculos das 10h (VisBusinessSendResumesToRecruiters,
# job jobsnow-curriculos-aos-recrutadores). Ate 2026-11-24 o numero era fixo no codigo (RECRUITERS_PER_DAY = 2000);
# agora o processo le o registro por id e, sem ele, falha. O id e o SHA-1 do systemMessageName, como em
# CcpEntity.calculateId (hexadecimal com sinal, sem zeros a esquerda). message e uma lista com um unico texto, o numero.
#
# Fases:
#   criar           ANTES do deploy do cron: grava 2000 so quando o registro nao existe (nao desfaz uma mudanca ja feita).
#   definir <n>     troca o numero, a qualquer momento. O cache da entidade (Memorystore) dura 1 hora: feita ate as 9h,
#                   a mudanca vale no envio das 10h do mesmo dia.
#   ver             so mostra o valor atual.
# Idempotente.
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 118-recrutadores-por-dia.py criar|ver [url do destino]
#      ES_DESTINO_AUTH=<valor do Authorization> python 118-recrutadores-por-dia.py definir 3000 [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

INDEX = "jn_system_parameter"
NAME = "com.vis.business.recruiter.resumes.VisRecruiterResumesSystemParameters.recruitersPerDay"
DEFAULT_VALUE = "2000"

USAGE = "uso: python 118-recrutadores-por-dia.py criar|ver [url do destino] | definir <numero> [url do destino]"
if len(sys.argv) < 2 or sys.argv[1] not in ("criar", "definir", "ver"):
    raise SystemExit(USAGE)
phase = sys.argv[1]
rest = sys.argv[2:]
new_value = None
if phase == "definir":
    if not rest or not rest[0].isdigit() or int(rest[0]) <= 0:
        raise SystemExit(USAGE)
    new_value = str(int(rest[0]))
    rest = rest[1:]
target_url = rest[0].rstrip("/") if rest else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, missing_ok=False):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise SystemExit("%s %s %s: %s" % (method, path, error.code, error.read().decode("utf-8", "replace")[:600]))


def entity_id(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    # CcpHashDecorator: new BigInteger(digest).toString(16), com sinal e sem zeros a esquerda
    return format(int.from_bytes(digest, "big", signed=True), "x")


def current():
    found = call("GET", "/%s/_doc/%s" % (INDEX, entity_id(NAME)), missing_ok=True)
    return found["_source"]["message"] if found and found.get("found") else None


def write(value):
    record = {"systemMessageName": NAME, "message": [value]}
    result = call("PUT", "/%s/_doc/%s?refresh=true" % (INDEX, entity_id(NAME)), record)
    if current() != [value]:
        raise SystemExit("conferencia falhou")
    return result["result"]


print("destino:", call("GET", "/")["cluster_name"], "| fase:", phase, "| id:", entity_id(NAME))
before = current()
print("valor atual:", before)

if phase == "criar":
    if before is None:
        print("gravado:", write(DEFAULT_VALUE), DEFAULT_VALUE)
    else:
        print("ja existe, mantido")

if phase == "definir":
    print("gravado:", write(new_value), new_value)

print("valor final:", current())
