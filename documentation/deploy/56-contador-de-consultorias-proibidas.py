# Carga do contador de consultorias proibidas (2026-11-11): le todos os vis_resume (so os ativos; a gemea
# vis_inactive_resume nao conta) e grava em jn_grouper o unico grupo de VisEntityVirtualNotAllowedCompanyCounter, cujo
# child e um texto JSON {"<dominio de notAllowedCompany>": <quantos curriculos ativos o proibem>}. E o que o decorator
# JnGrouperChildCurrentCounterEntityBeforeWrite mantem a cada escrita do curriculo depois do deploy da vis; os
# curriculos ja gravados so entram por esta carga. As chaves seguem VisResumeNotAllowedCompanyCounterKeys: o texto como
# foi digitado, sem aspas e barras invertidas, uma vez por curriculo, sem vazias.
# Idempotente: recalcula do zero e sobrescreve o grupo (a contagem e o estado atual). Sem nenhum dominio, apaga o grupo.
# Ids calculados pelo framework (VisEntityVirtualNotAllowedCompanyCounter.getParentId e JnEntityGrouper.calculateId).
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 56-contador-de-consultorias-proibidas.py
#      ou: ES_DESTINO_AUTH=<valor> python 56-contador-de-consultorias-proibidas.py [destino]
# Imprime o relatorio das consultorias (mais rejeitadas primeiro); nao imprime e-mails de candidatos.
import json
import os
import sys
import urllib.error
import urllib.request

GROUP_ID = "5c2416527f73efb4a77b2e5fc545b60299ee1b40"
PARENT_ID = "1cb239585190afdf1cdda1a055a96a1a62a1ba9d"
PARENT_NAME = "vis_virtual_not_allowed_company_counter"
CHILD_NAME = "vis_resume"
FIELD = "notAllowedCompany"

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


def resumes():
    status, page = call("POST", "/vis_resume/_search?scroll=2m", {"size": 500, "_source": [FIELD]})
    if status != 200:
        print("falha ao ler vis_resume:", status, page)
        sys.exit(1)
    while page["hits"]["hits"]:
        for hit in page["hits"]["hits"]:
            yield hit["_source"]
        status, page = call("POST", "/_search/scroll", {"scroll": "2m", "scroll_id": page["_scroll_id"]})
    call("DELETE", "/_search/scroll", {"scroll_id": page["_scroll_id"]})


counters = {}
total = 0
with_domains = 0
for source in resumes():
    total += 1
    keys = []
    for value in source.get(FIELD) or []:
        key = str(value).replace('"', "").replace("\\", "")
        if key and key not in keys:
            keys.append(key)
    if keys:
        with_domains += 1
    for key in keys:
        counters[key] = counters.get(key, 0) + 1

if not counters:
    status, _ = call("DELETE", "/jn_grouper/_doc/" + GROUP_ID + "?refresh=true")
    print("nenhum dominio proibido em", total, "curriculos; grupo apagado (status", status, ")")
    sys.exit(0)

child = json.dumps(counters, ensure_ascii=False, separators=(",", ":"))
group = {
    "parentId": PARENT_ID,
    "parentName": PARENT_NAME,
    "childName": CHILD_NAME,
    "parentJson": {"counter": FIELD},
    "child": [child],
    "childCount": len(counters),
}
status, answer = call("PUT", "/jn_grouper/_doc/" + GROUP_ID + "?refresh=true", group)
print("gravado:", status, answer.get("result"))
status, stored = call("GET", "/jn_grouper/_doc/" + GROUP_ID)
same = stored.get("_source") == group
print("conferido:", same, "| curriculos ativos:", total, "| com consultoria proibida:", with_domains, "| consultorias:", len(counters))
print("RELATORIO")
for domain, count in sorted(counters.items(), key=lambda item: (-item[1], item[0].lower())):
    print(f"{count}\t{domain}")
sys.exit(0 if same else 1)
