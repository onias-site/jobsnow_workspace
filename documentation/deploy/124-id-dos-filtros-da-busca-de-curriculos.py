# Id dos filtros da busca de curriculos sem o dia (2026-11-26): vis_resume_filter ganha o campo id, a chave primaria, o
# SHA-1 dos filtros com as chaves (do json e dos json internos) em ordem alfabetica; o json deixa de ser chave. O link da
# busca (?filtro=<id>) passa a valer 24 horas depois da ultima busca dos filtros: no dia, pelo documento do dia; no dia
# seguinte, pela copia em jn_disposable_record (uma busca as 23:59 abre ate as 23:59 do dia seguinte). Antes, o id era o
# do documento do dia, e o link morria na virada do dia.
#
# O que faz: acrescenta o campo id (keyword) ao mapeamento de vis_resume_filter em producao e confere que ficou igual ao
# do local. Idempotente. Os documentos antigos (sem id) ficam como estao e saem com o expurgo do dia deles; os links
# antigos deixam de abrir os filtros (a tela nao faz nada), o que ja aconteceria na virada do dia.
#
# Ordem: rodar ANTES do deploy da vis e dos consumidores (o indice e strict: sem o campo, a gravacao dos filtros falha).
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 124-id-dos-filtros-da-busca-de-curriculos.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import json
import os
import sys
import urllib.error
import urllib.request

target = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                           "elasticsearch", "scripts", "entities", "create", "vis_resume_filter")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(target + path, data=data, method=method, headers={"Content-Type": "application/json"})
    auth = os.environ.get("ES_DESTINO_AUTH", "")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


with open(create_file, encoding="utf-8") as source:
    expected = json.load(source)["mappings"]

status, answer = call("PUT", "/vis_resume_filter/_mapping", {"properties": {"id": expected["properties"]["id"]}})
print("PUT _mapping", status, answer)
if status != 200:
    sys.exit(1)

status, answer = call("GET", "/vis_resume_filter/_mapping")
current = answer["vis_resume_filter"]["mappings"]
print("mapeamento:", json.dumps(current, sort_keys=True))
if current != expected:
    print("DIFERENTE do local:", json.dumps(expected, sort_keys=True))
    sys.exit(1)
print("igual ao local")
