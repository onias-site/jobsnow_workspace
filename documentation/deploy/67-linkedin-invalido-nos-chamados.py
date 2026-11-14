# LinkedIn invalido na tela de Chamados (2026-11-13): o reporte do recrutador passa a ser gravado em
# vis_invalid_linkedin_report (VisEntityInvalidLinkedinReport), filho do grupo jn_login_email do jn_grouper, e a resposta
# do operador o move para a gemea vis_invalid_linkedin_report_solved, com o texto em supportResponse.
# Este script leva a producao:
#   1. os indices novos vis_invalid_linkedin_report e vis_invalid_linkedin_report_solved, com o mapeamento do arquivo de
#      criacao do local;
#   2. as sementes de 67-sementes-linkedin-invalido-nos-chamados.jsonl (mesmo id do local): os textos
#      reportAnsweredInvalid e reportAnsweredValid de VisSupportVerifyLinkedinMessages em jn_system_message (regra "igual").
# As prioridades novas (duvida 3, sugestao 3, LinkedIn invalido 2) estao no codigo e nao precisam de script.
# Roda ANTES do deploy da API vis e dos consumidores. Idempotente.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 67-linkedin-invalido-nos-chamados.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 67-linkedin-invalido-nos-chamados.py
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_dir = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                          "elasticsearch", "scripts", "entities", "create")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

MAPPING_FILE = "vis_invalid_linkedin_report"
NEW_INDEXES = ["vis_invalid_linkedin_report", "vis_invalid_linkedin_report_solved"]


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
failures = 0

# 1. indices novos
with open(os.path.join(create_dir, MAPPING_FILE), encoding="utf-8") as source:
    definition = json.load(source)
for index in NEW_INDEXES:
    status, _ = call("HEAD", "/" + index)
    if status == 404:
        status, answer = call("PUT", "/" + index, definition)
        print("criado %s: %s" % (index, status))
    status, mapping = call("GET", "/%s/_mapping" % index)
    mappings = mapping[index]["mappings"]
    same = mappings.get("properties") == definition["mappings"]["properties"] and mappings.get("dynamic") == "strict"
    failures += 0 if same else 1
    print("%-36s mapeamento igual ao local: %s" % (index, same))

# 2. sementes
with open(os.path.join(here, "67-sementes-linkedin-invalido-nos-chamados.jsonl"), encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
for seed in seeds:
    index = seed["index"]
    path = "/%s/_doc/%s" % (index, urllib.parse.quote(seed["id"], safe=""))
    source = seed["source"]
    status, answer = call("PUT", path + "?refresh=true", source)
    status, written = call("GET", path)
    ok = status == 200 and written.get("_source") == source
    failures += 0 if ok else 1
    print("%-20s %s %s" % (index, seed["id"][:42], "ok" if ok else "FALHOU"))
print("sementes: %d" % len(seeds))
sys.exit(1 if failures else 0)
