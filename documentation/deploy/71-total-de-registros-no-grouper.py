# Total de registros no jn_grouper (2026-11-14): o decorator de @CcpEntityRecordsCounter (JnRecordsCounterEntity) e a
# entidade jn_records_count (JnEntityRecordsCount) foram eliminados. No lugar, @CcpEntityGrouperChildTotal
# (JnGrouperChildTotalEntity) guarda o total de cada ponta da entidade como child de um grupo: parentName
# jn_virtual_records_total (JnEntityVirtualRecordsTotal, parentJson {"entity": "vis_resume"}), childName vis_resume,
# child ["{\"total\":n}"], childCount 1. A ponta principal (vis_resume, ativos) fica no jn_grouper e a gemea
# (vis_inactive_resume, inativos) no jn_inactive_grouper, com o mesmo parentId e childName. Cada escrita soma a
# diferenca (+1/-1), entao os registros ja gravados precisam desta carga.
# Este script:
#   1. conta vis_resume e vis_inactive_resume e grava (sobrescrevendo) os 2 grupos; total 0 apaga o grupo;
#   2. apaga o indice jn_records_count, so se houver no repositorio de snapshots um snapshot SUCCESS das ultimas 36 h
#      que o contenha (sem ele, nao apaga e sai com 1).
# Roda DEPOIS do deploy da vis e dos consumidores: antes, o codigo antigo ainda grava em jn_records_count; e uma escrita
# entre o deploy e esta carga e absorvida, porque a carga grava o total absoluto.
# Idempotente: regrava os grupos com a contagem do momento; o indice ja apagado so e informado.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 71-total-de-registros-no-grouper.py
#      ou: ES_DESTINO_AUTH=<valor> python 71-total-de-registros-no-grouper.py [destino] [repositorio de snapshots]
# Imprime so contagens.
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "jn_virtual_records_total"
MAIN = "vis_resume"
TWIN = "vis_inactive_resume"
OLD_INDEX = "jn_records_count"
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
repository = sys.argv[2] if len(sys.argv) > 2 else "jobsnow-backup"
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


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def count(index):
    call("POST", "/" + index + "/_refresh")
    status, answer = call("GET", "/" + index + "/_count")
    if status != 200:
        print("falha ao contar", index, status, answer.get("error", {}).get("type"))
        sys.exit(1)
    return answer["count"]


failures = 0
parent_json = {"entity": MAIN}
parent_id = ccp_id(parent_json)
group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": MAIN})
print("grouper\tindice contado\ttotal\tgravado")
for grouper, index in (("jn_grouper", MAIN), ("jn_inactive_grouper", TWIN)):
    total = count(index)
    path = "/" + grouper + "/_doc/" + urllib.parse.quote(group_id, safe="")
    if total == 0:
        call("DELETE", path + "?refresh=true")
        print(f"{grouper}\t{index}\t0\tgrupo apagado")
        continue
    group = {
        "parentId": parent_id,
        "parentName": PARENT_NAME,
        "childName": MAIN,
        "parentJson": parent_json,
        "child": [json.dumps({"total": total}, separators=(",", ":"))],
        "childCount": 1,
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar o grupo em", grouper, status, answer.get("error", {}).get("type"))
        continue
    status, stored = call("GET", path)
    print(f"{grouper}\t{index}\t{total}\t{stored.get('_source', {}).get('child')}")

status, _ = call("HEAD", "/" + OLD_INDEX)
if status == 404:
    print(OLD_INDEX, "ja nao existe")
else:
    status, answer = call("GET", "/_snapshot/" + repository + "/_all")
    snapshots = answer.get("snapshots", []) if status == 200 else []
    limit = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=36)).timestamp() * 1000
    recent = [s for s in snapshots if s.get("state") == "SUCCESS" and OLD_INDEX in s.get("indices", [])
              and s.get("start_time_in_millis", 0) >= limit]
    if not recent:
        failures += 1
        print("sem snapshot SUCCESS das ultimas 36 h com", OLD_INDEX, "em", repository, "(status", status, "): indice mantido")
    else:
        print("snapshot com", OLD_INDEX + ":", recent[-1]["snapshot"])
        status, answer = call("DELETE", "/" + OLD_INDEX)
        if status != 200:
            failures += 1
            print("falha ao apagar", OLD_INDEX, status, answer.get("error", {}).get("type"))
        else:
            print(OLD_INDEX, "apagado")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
