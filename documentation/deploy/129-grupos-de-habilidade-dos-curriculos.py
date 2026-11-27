# Carga dos grupos de habilidade dos curriculos (2026-11-26): le os vis_resume ja gravados (ativos -> jn_grouper) e os
# vis_inactive_resume (inativos -> jn_inactive_grouper) e grava, para cada habilidade, o grupo de
# VisEntityVirtualSkillGrouper (parentName vis_virtual_skill_grouper, parentJson {"skill": ...}) cujo child e a lista dos
# ids dos curriculos que tem a habilidade, direta (itens de skill com category skillsFromText) ou indiretamente (a lista
# parent desses itens, os ancestrais da habilidade, e os itens de category parent). As habilidades excluidas e as
# descartadas ficam de fora. E o que VisResumeSkillCombinations + o decorator de @CcpEntityGrouperChild mantem a cada
# escrita do curriculo depois do deploy da vis e dos consumidores; os curriculos ja gravados so entram por esta carga.
# Cruzar os grupos de varias habilidades (uma leitura por id de cada) da os curriculos que tem todas elas.
# Idempotente: recalcula cada grupo do zero e o sobrescreve; apaga os grupos de habilidade sem curriculo (so os grupos
# de vis_virtual_skill_grouper sao tocados). Rodar logo depois do deploy: um curriculo salvo durante a carga pode ficar
# com a versao lida pela carga ate a proxima gravacao dele.
# Ids calculados como o framework (CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, escrito por
# CcpHashDecorator.asString), o mesmo calculo do script 59.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 129-grupos-de-habilidade-dos-curriculos.py
#      ou: ES_DESTINO_AUTH=<valor> python 129-grupos-de-habilidade-dos-curriculos.py [destino]
#      (sem destino: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://localhost:9200)
# Imprime so contagens e as habilidades com mais curriculos; nao imprime e-mails nem dados dos candidatos.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_skill_grouper"
CHILD_NAME = "vis_resume"
CATEGORIES = ("skillsFromText", "parent")
SIDES = [("vis_resume", "jn_grouper"), ("vis_inactive_resume", "jn_inactive_grouper")]

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
    if status == 404:
        return
    if status != 200:
        print("falha ao ler", index, status, page)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def skills_of(source):
    # VisResumeSkillCombinations: skill e parent dos itens de category skillsFromText ou parent, cada um uma vez
    skills = []
    for item in source.get("skill") or []:
        if not isinstance(item, dict) or item.get("category") not in CATEGORIES:
            continue
        for name in [item.get("skill")] + list(item.get("parent") or []):
            if name and name not in skills:
                skills.append(name)
    return skills


def path_of(index, group_id):
    return "/" + index + "/_doc/" + urllib.parse.quote(group_id, safe="")


failures = 0
report = {}
print("lado\tcurriculos\tsem habilidade\thabilidades\tgrupos apagados\tchildren gravados\tconferidos")
for resume_index, grouper_index in SIDES:
    children_by_skill = {}
    total = 0
    without_skill = 0
    for hit in scroll(resume_index, {"size": 500, "_source": ["skill"]}):
        total += 1
        skills = skills_of(hit["_source"])
        if not skills:
            without_skill += 1
        for skill in skills:
            children_by_skill.setdefault(skill, []).append(hit["_id"])

    expected = {}
    children_count = 0
    for skill, children in children_by_skill.items():
        parent_id = ccp_id({"skill": skill})
        group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": CHILD_NAME})
        expected[group_id] = children
        group = {
            "parentId": parent_id,
            "parentName": PARENT_NAME,
            "childName": CHILD_NAME,
            "parentJson": {"skill": skill},
            "child": children,
            "childCount": len(children),
        }
        status, answer = call("PUT", path_of(grouper_index, group_id), group)
        if status not in (200, 201):
            failures += 1
            print("falha ao gravar um grupo em", grouper_index, status, answer.get("error", {}).get("type"))
            continue
        children_count += len(children)
        if grouper_index == "jn_grouper":
            report[skill] = len(children)

    # os grupos de habilidades que nenhum curriculo deste lado tem mais
    deleted = 0
    old_groups = {"size": 500, "_source": False, "query": {"term": {"parentName": PARENT_NAME}}}
    for hit in list(scroll(grouper_index, old_groups)):
        if hit["_id"] in expected:
            continue
        status, _ = call("DELETE", path_of(grouper_index, hit["_id"]))
        if status == 200:
            deleted += 1
        elif status != 404:
            failures += 1
            print("falha ao apagar um grupo em", grouper_index, status)
    call("POST", "/" + grouper_index + "/_refresh")

    checked = 0
    for group_id, children in expected.items():
        status, stored = call("GET", path_of(grouper_index, group_id))
        if status == 200 and stored.get("_source", {}).get("child") == children:
            checked += 1
        else:
            failures += 1
    print(f"{grouper_index}\t{total}\t{without_skill}\t{len(expected)}\t{deleted}\t{children_count}\t{checked}")

print("AS 20 HABILIDADES COM MAIS CURRICULOS ATIVOS")
for skill, count in sorted(report.items(), key=lambda item: (-item[1], item[0]))[:20]:
    print(f"{count}\t{skill}")
print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
