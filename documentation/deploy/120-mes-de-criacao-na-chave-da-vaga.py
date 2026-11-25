# Mes de criacao na chave da vaga (2026-11-24): a chave de vis_position passa a ser o recrutador, o titulo e o yearMonth
# (yyyyMM, o mes da criacao, fixado no primeiro save e mantido pelas edicoes, renomeios e idas e voltas da gemea). O mesmo
# recrutador pode repetir um titulo em outro mes, nunca no mesmo. A edicao pode trocar o titulo (a vaga do titulo antigo
# some sem rastro, por deleteAnyWhere, e os curriculos ja enviados a ela vao para a nova pela fila
# VisBusinessMoveTheResumesSentToTheRenamedPosition); a lista do ultimo e-mail de cada vaga (vis_position_resumes) usa a
# mesma chave.
#
# O que faz:
#   1. acrescenta o campo yearMonth (keyword) em vis_position, vis_inactive_position e vis_position_resumes, todos
#      dynamic strict: sem o campo no mapeamento, o save da vaga falha;
#   2. conta os registros dos tres indices: os gravados antes nao tem o yearMonth e o id deles foi calculado sem ele, entao
#      a API nova nao os acha. Em 2026-11-24 producao tinha 0 vagas, 0 excluidas e 0 listas; se houver algum, o script
#      avisa e sai com 1 (precisaria de migracao: regravar com o mes da insertionDate e o id novo).
# Imprime so contagens. Idempotente.
#
# Ordem: ANTES do deploy da vis, dos consumidores e do cron. Rodar tambem 03-criar-filas.ps1 (fila nova
# com.vis.business.position.VisBusinessMoveTheResumesSentToTheRenamedPosition, linha de documentation/deploy/topicos.tsv).
# Depois: o cache das entidades dura 1 hora.
#
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python 120-mes-de-criacao-na-chave-da-vaga.py [url do destino]
#      (sem url: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
import json
import os
import sys
import urllib.error
import urllib.request

target = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
INDICES = ["vis_position", "vis_inactive_position", "vis_position_resumes"]
FIELD = {"yearMonth": {"type": "keyword"}}


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


problems = 0
for index in INDICES:
    status, _ = call("HEAD", "/" + index)
    if status == 404:
        print(f"{index}: indice inexistente")
        problems += 1
        continue
    status, answer = call("PUT", f"/{index}/_mapping", {"properties": FIELD})
    status, mapping = call("GET", f"/{index}/_mapping")
    field = mapping[index]["mappings"]["properties"].get("yearMonth")
    status, count = call("GET", f"/{index}/_count")
    total = count.get("count", -1)
    status, without = call("POST", f"/{index}/_count", {"query": {"bool": {"must_not": {"exists": {"field": "yearMonth"}}}}})
    missing = without.get("count", -1)
    print(f"{index}: campo yearMonth {field}; registros {total}; sem o mes {missing}")
    if field != FIELD["yearMonth"] or missing != 0:
        problems += 1

print("pendencias:", problems)
sys.exit(1 if problems else 0)
