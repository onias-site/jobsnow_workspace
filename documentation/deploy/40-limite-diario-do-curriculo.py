# Limite diario das acoes sobre o curriculo salvo (2026-11-07): cria no destino o indice vis_resume_daily_action
# (VisEntityResumeDailyAction, descartavel diaria, PK email + action: inactivation, reactivation, exclusion, update),
# com o mapeamento do arquivo create/vis_resume_daily_action do ccp_rest-api-tests_jobsnow. Sem sementes: os registros
# nascem das acoes do candidato (regra nao-levar). Shards e replicas copiados do jn_ticket_daily_limit do proprio
# destino, a descartavel diaria que serviu de modelo.
# Rodar ANTES do deploy da API vis que usa o indice: sem ele, salvar, inativar, reativar e excluir curriculo falham.
# Idempotente: indice ja existente com o mesmo mapeamento so e conferido.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 40-limite-diario-do-curriculo.py [destino]
import json
import os
import sys
import urllib.error
import urllib.request

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
index = "vis_resume_daily_action"
model_index = "jn_ticket_daily_limit"
here = os.path.dirname(os.path.abspath(__file__))
mapping_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                            "elasticsearch", "scripts", "entities", "create", index)


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    with opener.open(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def exists(path):
    try:
        call("GET", path)
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


with open(mapping_file, encoding="utf-8") as file:
    expected_mappings = json.load(file)["mappings"]

print("destino:", call("GET", "/")["cluster_name"])

if exists("/" + index):
    print("%s ja existe" % index)
else:
    model_settings = call("GET", "/%s/_settings" % model_index)[model_index]["settings"]["index"]
    settings = {"number_of_shards": model_settings["number_of_shards"], "number_of_replicas": model_settings["number_of_replicas"]}
    result = call("PUT", "/" + index, {"settings": settings, "mappings": expected_mappings})
    print("%s criado: %s, settings %s" % (index, result.get("acknowledged"), settings))

written_mappings = call("GET", "/%s/_mapping" % index)[index]["mappings"]
same = "confere" if written_mappings == expected_mappings else "DIFERENTE: %s" % json.dumps(written_mappings)
print("mapeamento de %s: %s" % (index, same))
if written_mappings != expected_mappings:
    raise SystemExit(1)
