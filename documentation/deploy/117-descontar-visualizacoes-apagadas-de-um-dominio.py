# Desconta dos contadores historicos as visualizacoes de curriculo apagadas de um dominio de recrutador (2026-11-24).
# Motivo: em 2026-11-20 o script 100 apagou em producao as visualizacoes de curriculos@onias.site (recrutador de teste do
# proprio usuario), mas tres contadores do jn_grouper sao historicos (apagar ou desativar uma visualizacao nao subtrai) e
# continuaram contando-as: a tela Curiosidades mostrava onias.site com 52 visualizacoes quando so havia 1.
# Os contadores corrigidos, so na chave/grupos do dominio informado (os outros dominios ficam como estao):
#   1. vis_virtual_viewer_domain_counter (pizza "empresas que mais visualizam"): child {"<dominio>": n}; n passa a ser o
#      numero de visualizacoes que existem hoje (vis_viewed_resume + vis_inactive_viewed_resume) dos recrutadores do dominio;
#   2. vis_resume_views_of_the_month ("Quem me viu" de cada curriculo, por mes): child {"<dominio>": n}, n = recrutadores
#      distintos do dominio com visualizacao existente daquele curriculo naquele mes; chave zerada sai do child, grupo sem
#      chave nenhuma e apagado;
#   3. vis_virtual_resume_views_counter (total de visualizacoes do curriculo): child {"views": n}; desconta o que saiu do
#      grupo do mes do mesmo dono; grupo que chega a 0 e apagado.
# So diminui, nunca aumenta um contador. Os recrutadores do dominio vem de vis_recruiter, vis_inactive_recruiter e
# vis_recruiter_unsubscribed (o e-mail das visualizacoes e SHA-1; os e-mails de recrutadores apagados de vez nao sao
# conhecidos, entao as visualizacoes deles contam como inexistentes, que e o que se quer).
# Grava com controle de concorrencia (if_seq_no/if_primary_term) e refresh. Idempotente: rodar de novo nao muda nada.
# O cache das entidades (1 h) segura o valor antigo na API: publicar nova revisao da vis ou esperar a hora passar.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 117-descontar-visualizacoes-apagadas-de-um-dominio.py -Argumentos onias.site
#      ou: ES_DESTINO_AUTH=<valor> python 117-...py <dominio> [destino] [--simular]
#      local: python 117-...py onias.site http://127.0.0.1:9200
# Imprime so contagens, sem e-mails nem LinkedIns.
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

GROUPER = "jn_grouper"
CHILD_NAME = "vis_viewed_resume"
DOMAIN_COUNTER = "vis_virtual_viewer_domain_counter"
MONTHLY = "vis_resume_views_of_the_month"
VIEWS_COUNTER = "vis_virtual_resume_views_counter"
VIEW_INDEXES = ("vis_viewed_resume", "vis_inactive_viewed_resume")
RECRUITER_INDEXES = ("vis_recruiter", "vis_inactive_recruiter", "vis_recruiter_unsubscribed")

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
simulate = "--simular" in sys.argv[1:]
if not arguments:
    print("informe o dominio")
    sys.exit(2)
domain = arguments[0].lower()
target_url = arguments[1].rstrip("/") if len(arguments) > 1 else "http://127.0.0.1:9210"
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


def java_sha1(text):
    # CcpHashDecorator SHA1: BigInteger com sinal em hexadecimal, sem zeros a esquerda
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def scroll(index, body):
    status, page = call("POST", "/" + index + "/_search?scroll=10m&seq_no_primary_term=true", body)
    if status == 404:
        return
    if status != 200:
        print("falha ao ler", index, status)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit
        status, page = call("POST", "/_search/scroll", {"scroll": "10m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


def groups_of(parent_name):
    query = {"size": 1000, "query": {"bool": {"filter": [{"term": {"parentName": parent_name}}, {"term": {"childName": CHILD_NAME}}]}}}
    return list(scroll(GROUPER, query))


def counters_of(group):
    children = group["_source"].get("child") or ["{}"]
    return json.loads(children[0])


def parent_json_of(group):
    parent = group["_source"].get("parentJson") or {}
    return json.loads(parent) if isinstance(parent, str) else parent


def month_of(date):
    # dd/MM/yyyy HH:mm:ss
    return date[6:10] + date[3:5]


# 1. os recrutadores do dominio (SHA-1 do e-mail)
recruiters = set()
for index in RECRUITER_INDEXES:
    for hit in scroll(index, {"size": 1000, "_source": ["email"], "query": {"wildcard": {"email": "*@" + domain}}}):
        email = hit["_source"].get("email", "")
        if email.lower().endswith("@" + domain):
            recruiters.add(java_sha1(email))
print("recrutadores do dominio:", len(recruiters))

# 2. as visualizacoes que existem hoje desses recrutadores
emails_by_linkedin_hash = {}
for hit in scroll("vis_resume_linkedin", {"size": 2000, "_source": ["linkedinAddress", "emails"]}):
    address = hit["_source"].get("linkedinAddress")
    if address:
        emails_by_linkedin_hash[java_sha1(address)] = hit["_source"].get("emails") or []
live_views = 0
expected_monthly = {}  # (dono, yyyyMM) -> recrutadores distintos
for index in VIEW_INDEXES:
    for hit in scroll(index, {"size": 2000, "_source": ["email", "linkedin", "date"]}):
        source = hit["_source"]
        recruiter = source.get("email")
        if recruiter not in recruiters:
            continue
        live_views += 1
        month = month_of(str(source.get("date", "")))
        for owner in emails_by_linkedin_hash.get(source.get("linkedin"), []):
            expected_monthly.setdefault((owner, month), set()).add(recruiter)
print("visualizacoes existentes do dominio:", live_views)

operations = []  # (descricao, metodo, caminho, corpo)


def write(group, counters):
    source = dict(group["_source"])
    source["child"] = [json.dumps(counters, separators=(",", ":"))]
    source["childCount"] = len(counters)
    path = f"/{GROUPER}/_doc/{group['_id']}?if_seq_no={group['_seq_no']}&if_primary_term={group['_primary_term']}&refresh=true"
    return ("PUT", path, source)


def delete(group):
    path = f"/{GROUPER}/_doc/{group['_id']}?if_seq_no={group['_seq_no']}&if_primary_term={group['_primary_term']}&refresh=true"
    return ("DELETE", path, None)


# 3. pizza dos dominios
for group in groups_of(DOMAIN_COUNTER):
    counters = counters_of(group)
    old = int(counters.get(domain, 0))
    if old <= live_views:
        print("pizza dos dominios: ja correta", old)
        continue
    counters[domain] = live_views
    if live_views == 0:
        del counters[domain]
    print("pizza dos dominios:", old, "->", live_views)
    operations.append(write(group, counters))

# 4. Quem me viu de cada mes, e o quanto sai de cada dono
removed_by_owner = {}
monthly_changed = 0
monthly_deleted = 0
monthly_before = 0
monthly_after = 0
for group in groups_of(MONTHLY):
    counters = counters_of(group)
    if domain not in counters:
        continue
    parent = parent_json_of(group)
    owner = parent.get("email")
    month = str(parent.get("monthYear"))
    old = int(counters[domain])
    new = len(expected_monthly.get((owner, month), ()))
    monthly_before += old
    monthly_after += min(old, new)
    if new >= old:
        continue
    removed_by_owner[owner] = removed_by_owner.get(owner, 0) + old - new
    monthly_changed += 1
    counters[domain] = new
    if new == 0:
        del counters[domain]
    if not counters:
        monthly_deleted += 1
        operations.append(delete(group))
        continue
    operations.append(write(group, counters))
print("Quem me viu:", monthly_before, "->", monthly_after, "| grupos alterados:", monthly_changed, "| apagados (sem outra chave):", monthly_deleted)

# 5. total de visualizacoes por curriculo
views_before = 0
views_after = 0
views_deleted = 0
views_changed = 0
for group in groups_of(VIEWS_COUNTER):
    owner = parent_json_of(group).get("email")
    removed = removed_by_owner.get(owner, 0)
    if removed == 0:
        continue
    counters = counters_of(group)
    old = int(counters.get("views", 0))
    new = max(old - removed, 0)
    views_before += old
    views_after += new
    views_changed += 1
    if new == 0:
        views_deleted += 1
        operations.append(delete(group))
        continue
    counters["views"] = new
    operations.append(write(group, counters))
print("total por curriculo:", views_before, "->", views_after, "| grupos alterados:", views_changed, "| apagados (0):", views_deleted)

if simulate:
    print("SIMULACAO: nada gravado,", len(operations), "operacoes")
    sys.exit(0)

failures = 0
for method, path, body in operations:
    status, answer = call(method, path, body)
    if status not in (200, 201):
        failures += 1
        print("falha", method, status, (answer.get("error") or {}).get("type") if isinstance(answer.get("error"), dict) else answer.get("result"))
print("operacoes:", len(operations), "| falhas:", failures)
print("OK" if failures == 0 else "FALHAS (rodar de novo: so refaz o que faltou)")
print("cache das entidades: 1 h")
sys.exit(0 if failures == 0 else 1)
