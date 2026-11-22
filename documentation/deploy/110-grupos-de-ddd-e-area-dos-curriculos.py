# Carga dos grupos de ddd e area dos curriculos (2026-11-22): o endpoint publico da aba "Filtros" do formulario de vagas
# (GET positions/resumes-of-the-ddds/{resumeType}/{ddds}) passou a ler, em vez dos grupos de vis_virtual_ddd_grouper,
# os de vis_virtual_ddd_resume_type_grouper: um grupo por ddd e por area (resumeType) do curriculo, com o mesmo child do
# grupo por ddd (btc, clt, disponibility, experience, spokenLanguage, negotiableClaim, pcd, pj, resumeType,
# temporallyJobTime, travel, a lista skill das skillsFromResume e o id do curriculo). E o que o terceiro
# @CcpEntityGrouperChild de VisEntityResume mantem a cada escrita depois do deploy da vis e dos consumidores; os
# curriculos ja gravados so entram por esta carga.
# Le os vis_resume (ativos -> jn_grouper) e os vis_inactive_resume (inativos -> jn_inactive_grouper). Idempotente:
# recalcula cada grupo do zero e o sobrescreve; um par ddd/area sem curriculo tem o grupo apagado (so os grupos de
# vis_virtual_ddd_resume_type_grouper sao tocados). Rodar logo DEPOIS do deploy da vis e dos consumidores: um curriculo
# salvo durante a carga pode ficar com a versao lida por ela ate a proxima gravacao dele.
# Ids calculados como no framework (CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, unidos por ", ",
# em BigInteger com sinal na base 16), conferidos pela formula contra os ids do script 57.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 110-grupos-de-ddd-e-area-dos-curriculos.py
#      ou: ES_DESTINO_AUTH=<valor> python 110-grupos-de-ddd-e-area-dos-curriculos.py [destino]
# Imprime so contagens; nao imprime e-mails nem dados dos candidatos.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

PARENT_NAME = "vis_virtual_ddd_resume_type_grouper"
CHILD_NAME = "vis_resume"
CHILD_FIELDS = ["btc", "clt", "disponibility", "experience", "spokenLanguage", "negotiableClaim", "pcd", "pj", "resumeType",
                "temporallyJobTime", "travel"]
SIDES = [("vis_resume", "jn_grouper"), ("vis_inactive_resume", "jn_inactive_grouper")]
# os valores permitidos de VisJsonCommonsFields.ddd e de VisJsonCommonsFields.resumeType
DDDS = [10, 61, 62, 64, 65, 66, 67, 82, 71, 73, 74, 75, 77, 85, 88, 98, 99, 83, 81, 87, 86, 89, 84, 79, 68, 96, 92, 97, 91, 93, 94, 69, 95, 63, 27, 28, 31, 32, 33, 34, 35, 37, 38, 21, 22, 24, 11, 12, 13, 14, 15, 16, 17, 18, 19, 41, 42, 43, 44, 45, 46, 51, 53, 54, 55, 47, 48, 49]
RESUME_TYPES = [1, 2, 3, 4]


def java_sha1(text):
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def ccp_id(primary_key):
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    return java_sha1(text)


def group_ids(ddd, resume_type):
    parent_id = ccp_id({"ddd": ddd, "resumeType": resume_type})
    group_id = ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": CHILD_NAME})
    return parent_id, group_id


# a formula confere com os ids gravados pelo script 57 (grupo do ddd 10)
assert ccp_id({"ddd": 10}) == "-4e2a87eeee27b084c01ba5f7ad1a68a73285781b"
assert ccp_id({"parentId": ccp_id({"ddd": 10}), "parentName": "vis_virtual_ddd_grouper", "childName": CHILD_NAME}) == "-3dc33649314b530a3e2f933b23763ade46c09b55"

GROUPS = {(ddd, resume_type): group_ids(ddd, resume_type) for ddd in DDDS for resume_type in RESUME_TYPES}
target_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def skills_from_resume(source):
    # childFieldsProducers = VisResumeSkillsFromResumeChildField: skill.filter(x -> x.type == 'skillsFromResume').map(x -> x.skill)
    return [item.get("skill") for item in (source.get("skill") or []) if isinstance(item, dict) and item.get("type") == "skillsFromResume"]


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


def resumes(index):
    status, page = call("POST", "/" + index + "/_search?scroll=2m", {"size": 500, "_source": ["ddd"] + CHILD_FIELDS + ["skill"]})
    if status == 404:
        return
    if status != 200:
        print("falha ao ler", index, status, page)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit["_id"], hit["_source"]
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


failures = 0
print("lado\tcurriculos\tsem ddd ou area valida\tgrupos gravados\tgrupos apagados\tchildren gravados\tconferidos")
for resume_index, grouper_index in SIDES:
    children_by_group = {key: [] for key in GROUPS}
    total = 0
    without_group = 0
    for resume_id, source in resumes(resume_index):
        total += 1
        child = {field: source[field] for field in CHILD_FIELDS if field in source and source[field] is not None}
        child["skill"] = skills_from_resume(source)
        child["id"] = resume_id
        child_text = json.dumps(child, ensure_ascii=False, separators=(",", ":"))
        resume_type = to_int(source.get("resumeType"))
        keys = []
        for value in source.get("ddd") or []:
            key = (to_int(value), resume_type)
            if key in GROUPS and key not in keys:
                keys.append(key)
        if not keys:
            without_group += 1
        for key in keys:
            children_by_group[key].append(child_text)

    written = 0
    deleted = 0
    children_count = 0
    checked = 0
    for key, children in children_by_group.items():
        ddd, resume_type = key
        parent_id, group_id = GROUPS[key]
        path = "/" + grouper_index + "/_doc/" + group_id
        if not children:
            status, _ = call("DELETE", path)
            if status == 200:
                deleted += 1
            elif status != 404:
                failures += 1
                print("falha ao apagar o grupo do ddd", ddd, "area", resume_type, "em", grouper_index, status)
            continue
        group = {
            "parentId": parent_id,
            "parentName": PARENT_NAME,
            "childName": CHILD_NAME,
            "parentJson": {"ddd": ddd, "resumeType": resume_type},
            "child": children,
            "childCount": len(children),
        }
        status, answer = call("PUT", path, group)
        if status not in (200, 201):
            failures += 1
            print("falha ao gravar o grupo do ddd", ddd, "area", resume_type, "em", grouper_index, status, answer)
            continue
        written += 1
        children_count += len(children)
    call("POST", "/" + grouper_index + "/_refresh")
    for key, children in children_by_group.items():
        if not children:
            continue
        status, stored = call("GET", "/" + grouper_index + "/_doc/" + GROUPS[key][1])
        if status == 200 and stored.get("_source", {}).get("child") == children:
            checked += 1
        else:
            failures += 1
            print("grupo do ddd/area", key, "em", grouper_index, "nao confere:", status)
    print(f"{grouper_index}\t{total}\t{without_group}\t{written}\t{deleted}\t{children_count}\t{checked}")

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
