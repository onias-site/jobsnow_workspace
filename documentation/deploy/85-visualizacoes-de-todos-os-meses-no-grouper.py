# Visualizacoes de todos os meses no grouper (2026-11-15): a tela meu-recrutamento/curriculos-visualizados ganhou o
# checkbox "Listar todos", que le (GET recruiter/{email}/viewed-resumes/all) o grupo de TODAS as visualizacoes do
# recrutador, de qualquer mes: parentName vis_viewed_resumes_of_the_recruiter (VisEntityViewedResumesOfTheRecruiter,
# entidade virtual sem indice nem periodo), childName vis_viewed_resume, parentJson {"email": <SHA-1 do e-mail>}. O
# @CcpEntityGrouperChild de vis_viewed_resume (JnGrouperChildAsJsonEntityBeforeWrite) passou a manter esse grupo junto com
# o do mes: as visualizacoes da principal no jn_grouper (aba Visualizados), as da gemea vis_inactive_viewed_resume no
# jn_inactive_grouper (aba Indesejados), um item por curriculo (o da ultima visualizacao).
# O decorator so age nas escritas feitas depois do deploy. Este script monta os grupos novos a partir dos registros e dos
# grupos do mes (parentName vis_viewed_resumes_of_the_month, nos dois groupers), que sao os unicos que guardam o LinkedIn
# legivel (o registro guarda so o SHA-1):
#   - para cada registro de vis_viewed_resume (lado principal) e de vis_inactive_viewed_resume (lado gemeo), o item e o de
#     date mais recente, entre todos os meses e os dois groupers, cujo SHA-1 do linkedin e o do registro e cujo grupo e do
#     mesmo recrutador (parentJson.email = email do registro); o texto do item vai como esta;
#   - um item que ja esteja no grupo novo (gravado pelo decorator depois do deploy) entra na disputa: fica o de date mais
#     recente;
#   - so ficam no grupo de cada lado os itens de registros que estao naquele lado (um registro apagado de vez, ou que
#     mudou de lado, nao fica); grupo sem item e apagado.
# Registro sem item em nenhum grupo do mes (nao tem LinkedIn legivel em lugar nenhum) fica de fora e e contado.
# childCount = tamanho de child, como nos scripts do JnGroupers. Grava com controle de concorrencia (if_seq_no).
# Roda DEPOIS do deploy da vis e dos consumidores (antes, o codigo antigo nao mantem o grupo novo nas escritas e ele
# envelhece). Idempotente: rodar de novo recalcula e regrava so os grupos que mudaram.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 85-visualizacoes-de-todos-os-meses-no-grouper.py
#      ou: ES_DESTINO_AUTH=<valor> python 85-visualizacoes-de-todos-os-meses-no-grouper.py [destino] [--simular]
#      local: python 85-visualizacoes-de-todos-os-meses-no-grouper.py http://127.0.0.1:9200
# Imprime so contagens (nenhum e-mail, LinkedIn ou apelido).
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

MONTH_PARENT = "vis_viewed_resumes_of_the_month"
RECRUITER_PARENT = "vis_viewed_resumes_of_the_recruiter"
CHILD_NAME = "vis_viewed_resume"
GROUPERS = {False: "jn_grouper", True: "jn_inactive_grouper"}
VIEWS = {False: "vis_viewed_resume", True: "vis_inactive_viewed_resume"}
DATE_FORMAT = "%d/%m/%Y %H:%M:%S"
PAGE_SIZE = 1000

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
simulate = "--simular" in sys.argv[1:]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def search_all(index, query, source=True):
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
        body = {"size": PAGE_SIZE, "query": query, "_source": source, "seq_no_primary_term": True,
                "sort": [{"_shard_doc": "asc"}], "pit": {"id": pit_id, "keep_alive": "2m"}}
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


def sha1(text):
    # o mesmo texto do CcpHashDecorator.asString: o digest como BigInteger COM SINAL em base 16 (sem zeros a esquerda e
    # com "-" quando negativo), nao o hexdigest
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    return sha1(text)


def parse(child):
    try:
        return json.loads(child)
    except ValueError:
        return {}


def moment(child):
    try:
        return datetime.strptime(parse(child).get("date", ""), DATE_FORMAT)
    except ValueError:
        return datetime.min


def keep_the_latest(items, key, child):
    kept = items.get(key)
    if kept is None or moment(child) > moment(kept):
        items[key] = child


def collect_items(groups, items):
    # (hash do e-mail, hash do linkedin) -> texto do item de date mais recente
    for group in groups:
        email = group["_source"].get("parentJson", {}).get("email", "")
        for child in group["_source"].get("child", []):
            linkedin = parse(child).get("linkedin", "")
            if email and linkedin:
                keep_the_latest(items, (email, sha1(linkedin)), child)


def group_id_of(email):
    parent_id = ccp_id({"email": email})
    return parent_id, ccp_id({"parentId": parent_id, "parentName": RECRUITER_PARENT, "childName": CHILD_NAME})


def by_date(children):
    return sorted(children, key=moment, reverse=True)


month_query = {"bool": {"filter": [{"term": {"parentName": MONTH_PARENT}}, {"term": {"childName": CHILD_NAME}}]}}
recruiter_query = {"bool": {"filter": [{"term": {"parentName": RECRUITER_PARENT}}, {"term": {"childName": CHILD_NAME}}]}}

items = {}
month_groups = 0
existing = {}
for twin_side, grouper in GROUPERS.items():
    groups = search_all(grouper, month_query)
    month_groups += len(groups)
    collect_items(groups, items)
    for group in search_all(grouper, recruiter_query):
        existing[(twin_side, group["_id"])] = group
        collect_items([group], items)

records = {False: 0, True: 0}
without_item = {False: 0, True: 0}
wanted = {}
for twin_side, index in VIEWS.items():
    for record in search_all(index, {"match_all": {}}, ["email", "linkedin"]):
        records[twin_side] += 1
        email = record["_source"].get("email", "")
        linkedin_hash = record["_source"].get("linkedin", "")
        child = items.get((email, linkedin_hash))
        if child is None:
            without_item[twin_side] += 1
            continue
        wanted.setdefault((twin_side, email), []).append(child)

print(f"grupos do mes\t{month_groups}\titens distintos\t{len(items)}\tgrupos novos ja existentes\t{len(existing)}")
for twin_side, index in VIEWS.items():
    groups_of_the_side = sum(1 for side, _ in wanted if side == twin_side)
    print(f"{index}\t{records[twin_side]} registros\tsem item no grupo do mes\t{without_item[twin_side]}"
          f"\tgrupos a gravar no {GROUPERS[twin_side]}\t{groups_of_the_side}")

if simulate:
    print("simulacao: nada gravado")
    sys.exit(0)

written = unchanged = deleted = failures = 0
targets = {}
for (twin_side, email), children in wanted.items():
    parent_id, group_id = group_id_of(email)
    targets[(twin_side, group_id)] = (email, parent_id, by_date(children))
for (twin_side, group_id) in existing:
    targets.setdefault((twin_side, group_id), None)

for (twin_side, group_id), target in targets.items():
    grouper = GROUPERS[twin_side]
    path = "/" + grouper + "/_doc/" + urllib.parse.quote(group_id, safe="")
    current = existing.get((twin_side, group_id))
    concurrency = "" if current is None else f"&if_seq_no={current['_seq_no']}&if_primary_term={current['_primary_term']}"
    if target is None:
        # grupo novo que ja existia sem nenhum registro daquele lado: apagado, como o removeChildByKeys faz
        status, answer = call("DELETE", path + "?refresh=false" + concurrency)
        if status in (200, 404):
            deleted += 1
            continue
        failures += 1
        print("falha ao apagar um grupo do", grouper, status, answer.get("error", {}).get("type"))
        continue
    email, parent_id, children = target
    group = {"parentId": parent_id, "parentName": RECRUITER_PARENT, "childName": CHILD_NAME,
             "parentJson": {"email": email}, "child": children, "childCount": len(children)}
    if current is not None and current["_source"] == group:
        unchanged += 1
        continue
    operation = "&op_type=create" if current is None else concurrency
    status, answer = call("PUT", path + "?refresh=false" + operation, group)
    if status in (200, 201):
        written += 1
        continue
    failures += 1
    print("falha ao gravar um grupo do", grouper, status, answer.get("error", {}).get("type"))

for grouper in GROUPERS.values():
    call("POST", "/" + grouper + "/_refresh")
totals = []
for twin_side, grouper in GROUPERS.items():
    groups = search_all(grouper, recruiter_query)
    children = sum(len(group["_source"].get("child", [])) for group in groups)
    totals.append(f"{grouper}\t{len(groups)} grupos, {children} itens")
print(f"gravados\t{written}\tiguais\t{unchanged}\tapagados\t{deleted}\tfalhas\t{failures}")
print("\t".join(totals))
print("cache das entidades: 1 h; publique nova revisao da vis e reinicie os consumidores, ou espere a hora passar")
sys.exit(1 if failures else 0)
