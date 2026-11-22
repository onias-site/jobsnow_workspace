# E-mail que recebe os curriculos encontrados da vaga (2026-11-22): VisEntityPosition ganha o campo resumesEmail
# (keyword), preenchido pela tela com o e-mail do recrutador logado e obrigatorio salvo na frequencia "none". O
# mapeamento e strict: sem o campo, producao recusaria toda escrita da vaga nova.
# Acrescenta o campo por PUT _mapping em vis_position e na gemea vis_inactive_position. Campo novo nao mexe nos
# documentos que ja existem. O arquivo de mapeamento (usado pelo script 109) ja traz o campo: se o 109 rodar depois
# deste, o indice recriado tambem o tem.
# Idempotente: indice que ja tem o campo e pulado; indice que nao existe e avisado e pulado (o 109 o cria).
# Roda antes do deploy da vis.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 111-email-dos-curriculos-da-vaga.py
#      ou: ES_DESTINO_AUTH=<valor> python 111-email-dos-curriculos-da-vaga.py [destino]
import json
import os
import sys
import urllib.error
import urllib.request

INDEXES = ["vis_position", "vis_inactive_position"]
FIELD = "resumesEmail"
FIELD_MAPPING = {"type": "keyword"}

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
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


failures = 0
for index in INDEXES:
    status, answer = call("GET", "/" + index + "/_mapping")
    if status == 404:
        print(index + ": nao existe, pulado (o script 109 o cria com o campo)")
        continue
    if status != 200:
        print(index + ": erro ao ler o mapeamento, status " + str(status))
        failures += 1
        continue
    properties = answer[index]["mappings"].get("properties", {})
    if FIELD in properties:
        print(index + ": ja tem " + FIELD + " (" + properties[FIELD].get("type", "?") + "), pulado")
        continue
    status, answer = call("PUT", "/" + index + "/_mapping", {"properties": {FIELD: FIELD_MAPPING}})
    if status != 200:
        print(index + ": erro ao acrescentar " + FIELD + ", status " + str(status) + " " + json.dumps(answer)[:300])
        failures += 1
        continue
    status, answer = call("GET", "/" + index + "/_mapping")
    created = answer[index]["mappings"].get("properties", {}).get(FIELD, {})
    print(index + ": " + FIELD + " acrescentado (" + created.get("type", "?") + ")")

sys.exit(1 if failures else 0)
