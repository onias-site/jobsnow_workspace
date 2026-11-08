# Iguala ao ES local (9200) o mapeamento dos indices do destino (2026-11-08): o local e a VM rodam a mesma versao do
# Elasticsearch, e todo indice de producao tem de ter exatamente o mapeamento do local (decisao do usuario). Para cada
# indice informado, acrescenta no destino, por PUT /<indice>/_mapping, os campos e subcampos que existem so no local, com
# a definicao do local. Campo com tipo diferente nao muda no lugar (exige reindexar) e campo que existe so no destino nao
# se remove por _mapping: os dois sao so apontados. Primeira leva: o headers.userAgent de jn_http_api_error_client,
# jn_http_api_error_server e jn_http_api_retry_send_request, subcampo que o ES local criou sozinho dentro do objeto
# headers (dynamic: true) e que producao ainda nao tinha.
# Idempotente: rodar de novo, sem diferenca, nao grava nada. Confere no fim.
# Segunda leva: os subcampos de json em jn_disposable_record e jb_bot_command_step_session (INDICES=...).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 43-igualar-mapeamentos-ao-local.py [destino] [origem] [indice,...]
#      (a lista de indices tambem vem da variavel INDICES, para rodar pelo com-tunel-de-producao.ps1)
import json
import os
import sys
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
source_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://127.0.0.1:9200"
default_indexes = "jn_http_api_error_client,jn_http_api_error_server,jn_http_api_retry_send_request"
indexes = (sys.argv[3] if len(sys.argv) > 3 else os.environ.get("INDICES", default_indexes)).split(",")
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(url, method, path, body=None, authorization=""):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def mapping(url, index, authorization=""):
    answer = call(url, "GET", "/%s/_mapping" % index, None, authorization)
    return list(answer.values())[0]["mappings"].get("properties", {})


def missing(source, target, path, conflicts, extras):
    """The part of the source properties absent from the target, keeping the parents of each missing field."""
    result = {}
    for name, definition in source.items():
        field = path + name
        if name not in target:
            result[name] = definition
            continue
        target_definition = target[name]
        source_type = definition.get("type", "object")
        target_type = target_definition.get("type", "object")
        if source_type != target_type:
            conflicts.append("%s: %s na origem, %s no destino" % (field, source_type, target_type))
            continue
        inner = missing(definition.get("properties", {}), target_definition.get("properties", {}), field + ".", conflicts, extras)
        if inner:
            result[name] = {"properties": inner}
    for name in target:
        if name not in source:
            extras.append(path + name)
    return result


print("origem:", call(source_url, "GET", "/")["cluster_name"])
print("destino:", call(target_url, "GET", "/", None, auth)["cluster_name"])
pending = 0
for index in indexes:
    conflicts = []
    extras = []
    to_add = missing(mapping(source_url, index), mapping(target_url, index, auth), "", conflicts, extras)
    if to_add:
        call(target_url, "PUT", "/%s/_mapping" % index, {"properties": to_add}, auth)
        print("%s: acrescentado %s" % (index, json.dumps(to_add)))
    after_conflicts = []
    after_extras = []
    still_missing = missing(mapping(source_url, index), mapping(target_url, index, auth), "", after_conflicts, after_extras)
    print("%s: %s" % (index, "confere" if not still_missing else "AINDA FALTA %s" % json.dumps(still_missing)))
    for conflict in after_conflicts:
        print("   tipo diferente (exige reindexar):", conflict)
    for extra in after_extras:
        print("   so no destino (nao se remove por _mapping):", extra)
    pending += 1 if still_missing else 0
sys.exit(1 if pending else 0)
