# Carga do contador de habilidades evitadas (2026-11-12): le todos os vis_resume (so os ativos; a gemea
# vis_inactive_resume nao conta) e grava em jn_grouper, para cada habilidade excluida pelo dono do curriculo (os itens de
# skill cuja category e excludedSkills, pelo campo skill do item, uma vez por curriculo), o grupo de
# VisEntityVirtualExcludedSkillCounter (parentName vis_virtual_excluded_skill_counter, parentJson {"skill": ...}) cujo
# unico child e o texto JSON {"resumes": <quantos curriculos ativos a excluem>}. E o que o decorator
# JnGrouperChildCurrentCounterEntityBeforeWrite mantem a cada escrita do curriculo depois do deploy da vis e dos
# consumidores; os curriculos ja gravados so entram por esta carga.
# Idempotente: recalcula do zero e sobrescreve cada grupo (a contagem e o estado atual); apaga os grupos de habilidade
# que ninguem mais exclui (so os grupos de vis_virtual_excluded_skill_counter sao tocados).
# Ids calculados como o framework (CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, escrito por
# CcpHashDecorator.asString), conferidos contra o Java em 2026-11-12.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 59-contador-de-habilidades-evitadas.py
#      ou: ES_DESTINO_AUTH=<valor> python 59-contador-de-habilidades-evitadas.py [destino]
# Imprime o relatorio das habilidades mais evitadas (sem dados dos candidatos).
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_excluded_skill_counter"
CHILD_NAME = "vis_resume"
KEY = "resumes"
EXCLUDED_CATEGORY = "excludedSkills"

target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
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


def ccp_sha1(text):
    # BigInteger com sinal, em hexadecimal, sem os zeros a esquerda (CcpHashDecorator.asString)
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def ccp_id(primary_key):
    values = [str(primary_key[name]) for name in sorted(primary_key)]
    return ccp_sha1(", ".join(values))


def scroll(index, body):
    status, page = call("POST", "/" + index + "/_search?scroll=2m", body)
    if status != 200:
        print("falha ao ler", index, status, page)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


counters = {}
total = 0
excluding = 0
for hit in scroll("vis_resume", {"size": 500, "_source": ["skill"]}):
    total += 1
    skills = set()
    for item in hit["_source"].get("skill") or []:
        if isinstance(item, dict) and item.get("category") == EXCLUDED_CATEGORY and item.get("skill"):
            skills.add(item["skill"])
    if skills:
        excluding += 1
    for skill in skills:
        counters[skill] = counters.get(skill, 0) + 1

failures = 0
expected_ids = {}
for skill, count in counters.items():
    parent_id = ccp_id({"skill": skill})
    group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": CHILD_NAME})
    expected_ids[group_id] = skill
    group = {
        "parentId": parent_id,
        "parentName": PARENT_NAME,
        "childName": CHILD_NAME,
        "parentJson": {"skill": skill},
        "child": [json.dumps({KEY: count}, separators=(",", ":"))],
        "childCount": 1,
    }
    status, answer = call("PUT", "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe=""), group)
    if status not in (200, 201):
        failures += 1
        print("falha ao gravar um grupo:", status, answer.get("error", {}).get("type"))

# os grupos de habilidades que ninguem mais exclui
deleted = 0
old_groups = {"size": 500, "_source": False, "query": {"term": {"parentName": PARENT_NAME}}}
for hit in scroll("jn_grouper", old_groups):
    if hit["_id"] in expected_ids:
        continue
    status, _ = call("DELETE", "/jn_grouper/_doc/" + urllib.parse.quote(hit["_id"], safe=""))
    if status == 200:
        deleted += 1
    else:
        failures += 1
call("POST", "/jn_grouper/_refresh")

checked = 0
for group_id, skill in expected_ids.items():
    status, stored = call("GET", "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe=""))
    child = stored.get("_source", {}).get("child") or [""]
    if status == 200 and json.loads(child[0] or "{}").get(KEY) == counters[skill]:
        checked += 1
    else:
        failures += 1

print("curriculos ativos\tcom habilidade excluida\thabilidades\tgrupos apagados\tconferidos")
print(f"{total}\t{excluding}\t{len(counters)}\t{deleted}\t{checked}")
print("RELATORIO (curriculos ativos que excluem a habilidade)")
for skill, count in sorted(counters.items(), key=lambda item: (-item[1], item[0])):
    print(f"{count}\t{skill}")
print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
