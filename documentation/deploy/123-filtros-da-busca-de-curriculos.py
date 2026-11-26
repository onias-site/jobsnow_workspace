# Filtros da busca de curriculos (2026-11-25): a tela Curriculos -> Buscar e o modal da vaga gravam cada conjunto de
# filtros escolhido em vis_resume_filter (descartavel por dia, escrita assincrona pela fila da entidade; os mesmos filtros
# em qualquer ordem, inclusive das listas, sao um registro so), e a contagem dos
# curriculos fica 1 hora no cache sob o id dos filtros (POST /resume-filter, GET /resume-filter/{id} da vis).
#
# O que faz: cria em producao o indice vis_resume_filter com o mapeamento do local
# (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_resume_filter) e confere que ficou igual. Idempotente.
#
# Ordem: rodar ANTES do deploy da vis, dos consumidores e do front; rodar tambem 03-criar-filas.ps1 (fila da entidade
# assincrona com.vis.entities.VisEntityResumeFilter, linha nova em topicos.tsv). Sem o indice, o consumidor da fila falha
# ao gravar os filtros (a contagem na tela continua, mas o link com ?filtro= nao reabre os filtros).
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 123-filtros-da-busca-de-curriculos.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import json
import os
import sys
import urllib.error
import urllib.request

target = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
here = os.path.dirname(os.path.abspath(__file__))
create_folder = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                             "elasticsearch", "scripts", "entities", "create")
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


INDEX = "vis_resume_filter"
definition = json.load(open(os.path.join(create_folder, INDEX), encoding="utf-8"))
status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    print(INDEX, "criado:", status, answer.get("acknowledged"))
status, mapping = call("GET", "/" + INDEX + "/_mapping")
same = mapping[INDEX]["mappings"] == definition["mappings"]
print(INDEX, "mapeamento igual ao do local:", same)
if not same:
    raise SystemExit(1)
