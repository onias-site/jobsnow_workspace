# Criterios de ordem da vaga por idioma e por habilidade (2026-11-23): cada item do sort de VisEntityPosition passa a ter
# o campo value (keyword), o nome do idioma do criterio spokenLanguage ou da habilidade do criterio skill. O mapeamento
# do sort e strict: sem o subcampo, producao recusaria a vaga que ordena por idioma ou por habilidade.
# Acrescenta sort.value por PUT _mapping em vis_position e na gemea vis_inactive_position. Subcampo novo nao mexe nos
# documentos que ja existem. O arquivo de mapeamento local ja traz o subcampo.
# Idempotente: indice que ja tem o subcampo e pulado; indice que nao existe e avisado e pulado.
# Roda antes do deploy da vis.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 115-valor-do-criterio-de-ordem-da-vaga.py
#      ou: ES_DESTINO_AUTH=<valor> python 115-valor-do-criterio-de-ordem-da-vaga.py [destino]
import json
import os
import sys
import urllib.error
import urllib.request

INDEXES = ["vis_position", "vis_inactive_position"]
OBJECT = "sort"
FIELD = "value"
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


def sort_properties(answer, index):
    properties = answer[index]["mappings"].get("properties", {})
    return properties.get(OBJECT, {}).get("properties", {})


failures = 0
for index in INDEXES:
    status, answer = call("GET", "/" + index + "/_mapping")
    if status == 404:
        print(index + ": nao existe, pulado")
        continue
    if status != 200:
        print(index + ": erro ao ler o mapeamento, status " + str(status))
        failures += 1
        continue
    if FIELD in sort_properties(answer, index):
        print(index + ": ja tem " + OBJECT + "." + FIELD + ", pulado")
        continue
    body = {"properties": {OBJECT: {"properties": {FIELD: FIELD_MAPPING}}}}
    status, answer = call("PUT", "/" + index + "/_mapping", body)
    if status != 200:
        print(index + ": erro ao acrescentar " + OBJECT + "." + FIELD + ", status " + str(status) + " " + json.dumps(answer)[:300])
        failures += 1
        continue
    status, answer = call("GET", "/" + index + "/_mapping")
    created = sort_properties(answer, index).get(FIELD, {})
    print(index + ": " + OBJECT + "." + FIELD + " acrescentado (" + created.get("type", "?") + ")")

sys.exit(1 if failures else 0)
