# Descritivo da vaga no link da busca de curriculos (2026-11-26): na tela Curriculos -> Buscar, o texto da vaga passou
# para um modal ("Adicionar habilidades"), e "Copiar este link para enviar para alguem" com o texto preenchido e o usuario
# logado grava o texto em vis_resume_filter_description (PK filterId + email, description de 100 a 5000 caracteres;
# POST /recruiter/{email}/resume-filter-description da vis). O link ganha &email=<e-mail>, e o
# GET /resume-filter/{id}?email= devolve os filtros com o texto (union all de vis_resume_filter e
# vis_resume_filter_description).
#
# O que faz: cria o indice vis_resume_filter_description com o mapeamento do local
# (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_resume_filter_description) e confere que ficou igual.
# Idempotente. Sem seeds; a entidade e sincrona (nenhuma linha nova em topicos.tsv).
#
# Ordem: rodar ANTES do deploy da vis e do front. Sem o indice, copiar o link com o texto da 500.
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 128-descritivo-da-busca-de-curriculos.py [url do destino]
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


INDEX = "vis_resume_filter_description"
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
