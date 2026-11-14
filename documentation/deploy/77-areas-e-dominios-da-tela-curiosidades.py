# Tela Curiosidades, 2 pizzas novas (2026-11-14). Grava do zero no jn_grouper:
#   1. as areas dos curriculos ativos: parentName vis_virtual_resume_type_counter, parentJson {"counter": "resumeType"},
#      childName vis_resume, child {"<resumeType>": n} (VisEntityVirtualResumeTypeCounter, estado atual);
#   2. as visualizacoes de curriculos por dominio do recrutador: parentName vis_virtual_viewer_domain_counter, parentJson
#      {"counter": "domain"}, childName vis_viewed_resume, child {"<dominio>": n} (VisEntityVirtualViewerDomainCounter,
#      historico). O e-mail do recrutador so fica gravado como hash, entao o dominio vem dos grupos ja existentes de
#      vis_resume_views_of_the_month (visualizacoes do mes de cada curriculo por dominio), somados. Uma visualizacao de
#      um LinkedIn com mais de um e-mail de dono conta uma vez por e-mail, e os meses ja expurgados nao entram.
# Roda DEPOIS do deploy da vis e dos consumidores (antes dele, um curriculo ou visualizacao gravado pelo codigo antigo
# nao seria contado). Idempotente: sobrescreve os grupos. Nao cria indice nem campo.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 77-areas-e-dominios-da-tela-curiosidades.py
#      ou: ES_DESTINO_AUTH=<valor> python 77-areas-e-dominios-da-tela-curiosidades.py [destino]
# Imprime so contagens; os dominios sao de empresas (os pessoais ja vem juntos como freelancer).
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

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


def ccp_id(primary_key):
    # CcpEntity.calculateId: SHA-1 dos valores da chave em ordem de nome, BigInteger com sinal em hexadecimal
    text = ", ".join(str(primary_key[name]) for name in sorted(primary_key))
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    return format(int.from_bytes(digest, "big", signed=True), "x")


def scroll(index, body):
    status, page = call("POST", "/" + index + "/_search?scroll=10m", body)
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


def write_group(parent_name, parent_json, child_name, counts):
    parent_id = ccp_id(parent_json)
    group_id = ccp_id({"parentId": parent_id, "parentName": parent_name, "childName": child_name})
    path = "/jn_grouper/_doc/" + urllib.parse.quote(group_id, safe="")
    if not counts:
        call("DELETE", path)
        print(parent_name, "sem registros: grupo apagado")
        return 0
    ordered = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    group = {
        "parentId": parent_id,
        "parentName": parent_name,
        "childName": child_name,
        "parentJson": parent_json,
        "child": [json.dumps(ordered, separators=(",", ":"))],
        "childCount": len(ordered),
    }
    status, answer = call("PUT", path + "?refresh=true", group)
    if status not in (200, 201):
        print("falha ao gravar o grupo", parent_name, status, answer.get("error", {}).get("type"))
        return 1
    print("RELATORIO", parent_name, f"({len(ordered)} chaves, total {sum(ordered.values())}, as 10 maiores)")
    for key, count in list(ordered.items())[:10]:
        print(f"{key}\t{count}")
    return 0


failures = 0

# 1. as areas dos curriculos ativos
areas = {}
resumes = 0
for hit in scroll("vis_resume", {"size": 500, "_source": ["resumeType"]}):
    resumes += 1
    resume_type = hit["_source"].get("resumeType")
    if resume_type is None:
        continue
    key = str(int(float(resume_type)))
    areas[key] = areas.get(key, 0) + 1
print("vis_resume:", resumes, "curriculos ativos")
failures += write_group("vis_virtual_resume_type_counter", {"counter": "resumeType"}, "vis_resume", areas)

# 2. as visualizacoes por dominio, somando os grupos do mes de cada curriculo
domains = {}
groups = 0
query = {"size": 500, "query": {"term": {"parentName": "vis_resume_views_of_the_month"}}, "_source": ["child"]}
for hit in scroll("jn_grouper", query):
    groups += 1
    for child in hit["_source"].get("child", []):
        for domain, count in json.loads(child).items():
            domains[domain] = domains.get(domain, 0) + int(count)
print("vis_resume_views_of_the_month:", groups, "grupos")
failures += write_group("vis_virtual_viewer_domain_counter", {"counter": "domain"}, "vis_viewed_resume", domains)

print("OK" if failures == 0 else f"FALHAS: {failures}")
sys.exit(0 if failures == 0 else 1)
