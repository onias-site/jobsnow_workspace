# Cria no destino o indice vis_inactive_viewed_resume (2026-11-12): a gemea nova de vis_viewed_resume
# (VisEntityViewedResume), que recebe a visualizacao apagada da principal. O e-mail diario de curriculos aos recrutadores
# (VisBusinessSendResumesToRecruiters) nao manda mais ao recrutador o curriculo cuja visualizacao dele esta na gemea; um
# novo save da visualizacao a tira de la. A gemea usa o mesmo mapeamento da principal, que vem do arquivo de criacao do
# local (ccp_rest-api-tests_jobsnow/documentation/vis/.../create/vis_viewed_resume). Sem seeds.
# Roda ANTES do deploy da API vis e do processo diario: os dois leem ou gravam no indice (a leitura do processo diario
# falha sem ele).
# Idempotente: se o indice ja existe, so confere o mapeamento.
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 62-gemea-das-visualizacoes-de-curriculo.py [destino]
#      ou: powershell -File com-tunel-de-producao.ps1 -Script 62-gemea-das-visualizacoes-de-curriculo.py
import json
import os
import sys
import urllib.error
import urllib.request

INDEX = "vis_inactive_viewed_resume"
MAIN_INDEX = "vis_viewed_resume"
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
create_file = os.path.join(here, "..", "..", "ccp_rest-api-tests_jobsnow", "documentation", "vis", "database",
                           "elasticsearch", "scripts", "entities", "create", MAIN_INDEX)
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


with open(create_file, encoding="utf-8") as source:
    definition = json.load(source)
expected = definition["mappings"]["properties"]

status, _ = call("HEAD", "/" + INDEX)
if status == 404:
    status, answer = call("PUT", "/" + INDEX, definition)
    print("criado:", status, answer.get("acknowledged"))
    if status != 200:
        print(answer)
        sys.exit(1)
else:
    print("ja existia:", INDEX)

status, mapping = call("GET", "/" + INDEX + "/_mapping")
properties = mapping[INDEX]["mappings"].get("properties", {})
dynamic = mapping[INDEX]["mappings"].get("dynamic")
same = properties == expected and dynamic == "strict"
print("mapeamento igual ao local:", same, properties, "dynamic:", dynamic)
sys.exit(0 if same else 1)
