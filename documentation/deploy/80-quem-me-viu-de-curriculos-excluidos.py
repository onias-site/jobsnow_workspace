# "Quem me viu" de curriculos excluidos (2026-11-14): ate hoje, o delete everywhere do curriculo (o dono exclui todos os
# dados do curriculo) deixava no jn_grouper os grupos de contadores da tela "Quem me viu" (parentName
# vis_resume_views_of_the_month, childName vis_viewed_resume, parentJson {"email": <SHA-1 do dono>, "monthYear":
# yyyyMM}). Desde hoje VisBusinessDeleteTheViewersOfTheDeletedResume (@CcpAfterDeleteAnyWhereFromMainEntity de
# vis_resume) os apaga, mas os curriculos ja excluidos em producao deixaram os seus.
# Este script apaga do jn_grouper os grupos desse parentName cujo parentJson.email nao esta em vis_resume (ativos) nem em
# vis_inactive_resume (inativos: a desativacao mantem os contadores). Os grupos de contadores ficam so no jn_grouper
# (nunca no jn_inactive_grouper).
# Roda a qualquer momento (o codigo antigo nao recria grupo de curriculo excluido: o e-mail ja saiu do
# vis_resume_linkedin); o ideal e depois do deploy da vis e dos consumidores.
# Idempotente: rodar de novo nao acha mais nada para apagar.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 80-quem-me-viu-de-curriculos-excluidos.py
#      ou: ES_DESTINO_AUTH=<valor> python 80-quem-me-viu-de-curriculos-excluidos.py [destino] [--simular]
# Imprime so contagens (nenhum hash de e-mail).
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_resume_views_of_the_month"
CHILD_NAME = "vis_viewed_resume"
GROUPER = "jn_grouper"
RESUME_INDEXES = ("vis_resume", "vis_inactive_resume")
PAGE_SIZE = 1000

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
simulate = "--simular" in sys.argv[1:]
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


def search_all(index, query, source):
    # pagina por point in time e search_after (_shard_doc), para nao depender do limite de 10.000 do from/size
    call("POST", "/" + index + "/_refresh")
    status, answer = call("POST", "/" + index + "/_pit?keep_alive=2m")
    if status == 404:
        return []
    if status != 200:
        print("falha ao abrir a leitura de", index, status, answer.get("error", {}).get("type"))
        sys.exit(1)
    pit_id = answer["id"]
    hits = []
    after = None
    while True:
        body = {"size": PAGE_SIZE, "query": query, "_source": source, "sort": [{"_shard_doc": "asc"}],
                "pit": {"id": pit_id, "keep_alive": "2m"}}
        if after is not None:
            body["search_after"] = after
        status, answer = call("POST", "/_search", body)
        if status != 200:
            print("falha ao ler", index, status, answer.get("error", {}).get("type"))
            sys.exit(1)
        pit_id = answer.get("pit_id", pit_id)
        page = answer["hits"]["hits"]
        hits.extend(page)
        if len(page) < PAGE_SIZE:
            call("DELETE", "/_pit", {"id": pit_id})
            return hits
        after = page[-1]["sort"]


owners = set()
for index in RESUME_INDEXES:
    resumes = search_all(index, {"match_all": {}}, ["email"])
    print(f"{index}\t{len(resumes)} curriculos")
    for resume in resumes:
        owners.add(resume["_source"].get("email", ""))

groups_query = {"bool": {"filter": [{"term": {"parentName": PARENT_NAME}}, {"term": {"childName": CHILD_NAME}}]}}
groups = search_all(GROUPER, groups_query, ["parentJson"])
orphans = [group["_id"] for group in groups if group["_source"].get("parentJson", {}).get("email", "") not in owners]
print(f"{GROUPER}\t{len(groups)} grupos de {PARENT_NAME}\t{len(orphans)} de curriculos excluidos")

if simulate:
    print("simulacao: nada apagado")
    sys.exit(0)

failures = 0
for group_id in orphans:
    status, answer = call("DELETE", "/" + GROUPER + "/_doc/" + urllib.parse.quote(group_id, safe="") + "?refresh=true")
    if status not in (200, 404):
        failures += 1
        print("falha ao apagar um grupo", status, answer.get("error", {}).get("type"))

remaining = search_all(GROUPER, groups_query, ["parentJson"])
left = [group for group in remaining if group["_source"].get("parentJson", {}).get("email", "") not in owners]
print(f"apagados\t{len(orphans) - failures}\tfalhas\t{failures}\trestam de curriculos excluidos\t{len(left)}")
print("cache das entidades: 1 h; publique nova revisao da vis e reinicie os consumidores, ou espere a hora passar")
sys.exit(1 if failures or left else 0)
