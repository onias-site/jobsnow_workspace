# Total de visualizacoes por curriculo (2026-11-21): um contador novo em jn_grouper (@CcpEntityGrouperChildCounter de
# vis_viewed_resume com JnGrouperChildCounterOnBothSidesEntityBeforeWrite, um historico: cada recrutador conta 1 vez por
# curriculo, desativar ou apagar a visualizacao nao desconta, rever ou voltar da gemea nao soma de novo):
#   parentName vis_virtual_resume_views_counter, parentJson {"email": <SHA-1 do dono do curriculo>}, childName
#   vis_viewed_resume, child ["{\"views\":n}"], childCount 1. O parentId e o proprio id do curriculo (vis_resume).
#   Um grupo por e-mail que usa o LinkedIn visualizado (vis_resume_linkedin); LinkedIn sem curriculo nao conta.
# Este script recalcula do zero os grupos a partir das visualizacoes ja gravadas, nas duas pontas (vis_viewed_resume e
# vis_inactive_viewed_resume: a visualizacao que foi para a gemea continua contada). O LinkedIn da visualizacao esta em
# SHA-1; o do vis_resume_linkedin esta legivel, e o script calcula o mesmo SHA-1 para casar os dois.
# Roda DEPOIS do deploy da vis e dos consumidores (antes dele, uma visualizacao gravada pelo codigo antigo nao seria
# contada). Idempotente: sobrescreve os grupos (e apaga os de curriculos que nao tem mais visualizacao nenhuma).
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 108-total-de-visualizacoes-por-curriculo.py
#      ou: ES_DESTINO_AUTH=<valor> python 108-total-de-visualizacoes-por-curriculo.py [destino] [--simular]
# Imprime so contagens, sem dados pessoais.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_virtual_resume_views_counter"
CHILD_NAME = "vis_viewed_resume"
COUNTER_KEY = "views"
GROUPER = "jn_grouper"
VIEW_INDEXES = ("vis_viewed_resume", "vis_inactive_viewed_resume")
BULK_SIZE = 500

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
simulate = "--simular" in sys.argv[1:]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, path, body=None, raw=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/x-ndjson" if raw is not None else "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def java_sha1(text):
    # CcpHashDecorator SHA1: BigInteger com sinal em hexadecimal, sem zeros a esquerda (nunca o hexdigest)
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, unidos por ", "
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    return java_sha1(text)


def scroll(index, body):
    status, page = call("POST", "/" + index + "/_search?scroll=10m", body)
    if status == 404:
        print(index, "nao existe")
        return
    if status != 200:
        print("falha ao ler", index, status)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "10m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def group_id_of(hashed_email):
    parent_id = ccp_id({"email": hashed_email})
    return parent_id, ccp_id({"parentId": parent_id, "parentName": PARENT_NAME, "childName": CHILD_NAME})


# 1. os e-mails (SHA-1) de cada LinkedIn, pelo SHA-1 do endereco (o mesmo que a visualizacao guarda)
emails_by_linkedin_hash = {}
for hit in scroll("vis_resume_linkedin", {"size": 2000, "_source": ["linkedinAddress", "emails"]}):
    source = hit["_source"]
    address = source.get("linkedinAddress")
    if address:
        emails_by_linkedin_hash[java_sha1(address)] = source.get("emails") or []
print("vis_resume_linkedin enderecos:", len(emails_by_linkedin_hash))

# 2. cada visualizacao (um recrutador x um curriculo) conta 1 para cada e-mail do LinkedIn visto
views_by_email = {}
for index in VIEW_INDEXES:
    total = 0
    without_resume = 0
    for hit in scroll(index, {"size": 2000, "_source": ["linkedin"]}):
        total += 1
        emails = emails_by_linkedin_hash.get(hit["_source"].get("linkedin"), [])
        if not emails:
            without_resume += 1
            continue
        for hashed_email in emails:
            views_by_email[hashed_email] = views_by_email.get(hashed_email, 0) + 1
    print(index, "visualizacoes:", total, f"(de LinkedIn sem curriculo: {without_resume})")

# 3. os grupos que ja existem e nao tem mais visualizacao sao apagados
expected_ids = {group_id_of(hashed_email)[1] for hashed_email in views_by_email}
stale_ids = [hit["_id"] for hit in scroll(GROUPER, {"size": 2000, "_source": False, "query": {"bool": {"filter": [
    {"term": {"parentName": PARENT_NAME}}, {"term": {"childName": CHILD_NAME}}]}}})
    if hit["_id"] not in expected_ids]

lines = []
for hashed_email, views in views_by_email.items():
    parent_id, group_id = group_id_of(hashed_email)
    group = {
        "parentId": parent_id,
        "parentName": PARENT_NAME,
        "childName": CHILD_NAME,
        "parentJson": {"email": hashed_email},
        "child": [json.dumps({COUNTER_KEY: views}, separators=(",", ":"))],
        "childCount": 1,
    }
    lines.append(json.dumps({"index": {"_index": GROUPER, "_id": group_id}}))
    lines.append(json.dumps(group, separators=(",", ":")))
for stale_id in stale_ids:
    lines.append(json.dumps({"delete": {"_index": GROUPER, "_id": stale_id}}))

histogram = {}
for views in views_by_email.values():
    histogram[views] = histogram.get(views, 0) + 1
print("curriculos com visualizacao:", len(views_by_email), "| visualizacoes contadas:", sum(views_by_email.values()))
print("grupos a apagar (sem visualizacao):", len(stale_ids))
print("RELATORIO visualizacoes\tcurriculos")
for views in sorted(histogram):
    print(f"{views}\t{histogram[views]}")

if simulate:
    print("SIMULACAO: nada gravado")
    sys.exit(0)

failures = 0
step = 0
while step < len(lines):
    # um index ocupa 2 linhas, um delete 1: corta sem separar o par
    chunk = []
    operations = 0
    while step < len(lines) and operations < BULK_SIZE:
        line = lines[step]
        chunk.append(line)
        step += 1
        if '"index"' in line[:12]:
            chunk.append(lines[step])
            step += 1
        operations += 1
    payload = ("\n".join(chunk) + "\n").encode("utf-8")
    status, answer = call("POST", "/_bulk?refresh=true", raw=payload)
    if status != 200:
        print("falha no bulk", status, answer.get("error", {}).get("type"))
        sys.exit(1)
    for item in answer.get("items", []):
        result = item.get("index") or item.get("delete")
        if result.get("status") not in (200, 201, 404):
            failures += 1
print("falhas:", failures)
print("OK" if failures == 0 else "FALHAS")
print("cache das entidades: 1 h")
sys.exit(0 if failures == 0 else 1)
