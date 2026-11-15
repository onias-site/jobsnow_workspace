# Visualizacoes indesejadas no grouper inativo (2026-11-15): a tela meu-recrutamento/curriculos-visualizados ganhou duas
# abas, "Visualizados" (vis_viewed_resume, grupos do jn_grouper) e "Indesejados" (vis_inactive_viewed_resume, grupos do
# jn_inactive_grouper). Desde hoje JnGrouperChildAsJsonEntityBeforeWrite move o item do grupo do mes (parentName
# vis_viewed_resumes_of_the_month, childName vis_viewed_resume) para o outro lado do grouper quando a visualizacao muda de
# lado. As visualizacoes que ja estavam na gemea em producao (reporte de LinkedIn invalido, desde 2026-11-13) deixaram o
# item no jn_grouper.
# Este script, para cada registro de vis_inactive_viewed_resume, acha no jn_grouper o grupo do recrutador
# (parentJson.email = e-mail do registro, SHA-1) cujo item tem o LinkedIn do registro (SHA-1 do linkedin do item =
# linkedin do registro) e a mesma date (o grupo do mes da ultima visualizacao, como o decorator faz), tira o item de la
# (grupo vazio e apagado) e o poe no grupo de mesmo _id do jn_inactive_grouper (criado se nao existir), no lugar de uma
# versao anterior do mesmo LinkedIn. O texto do item vai como esta. childCount = tamanho de child, como nos scripts do
# JnGroupers.
# Roda DEPOIS do deploy da vis e dos consumidores (antes, a vis antiga nao le o jn_inactive_grouper e os consumidores
# antigos poriam de volta no jn_grouper um item regravado). Grava com controle de concorrencia (if_seq_no).
# Idempotente: rodar de novo nao acha mais item a mover.
# Uso: powershell -File com-tunel-de-producao.ps1 -Script 81-visualizacoes-indesejadas-no-grouper-inativo.py
#      ou: ES_DESTINO_AUTH=<valor> python 81-visualizacoes-indesejadas-no-grouper-inativo.py [destino] [--simular]
# Imprime so contagens (nenhum e-mail, LinkedIn ou apelido).
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PARENT_NAME = "vis_viewed_resumes_of_the_month"
CHILD_NAME = "vis_viewed_resume"
MAIN_GROUPER = "jn_grouper"
TWIN_GROUPER = "jn_inactive_grouper"
TWIN_VIEWS = "vis_inactive_viewed_resume"
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


def search_all(index, query):
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
        body = {"size": PAGE_SIZE, "query": query, "seq_no_primary_term": True, "sort": [{"_shard_doc": "asc"}],
                "pit": {"id": pit_id, "keep_alive": "2m"}}
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
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def parse(child):
    try:
        return json.loads(child)
    except ValueError:
        return {}


def items_to_move(main_groups, twin_views):
    # (id do grupo, texto do item, linkedin legivel) de cada item de visualizacao que esta na gemea
    wanted = {}
    for view in twin_views:
        source = view["_source"]
        wanted[(source.get("email", ""), source.get("linkedin", ""), source.get("date", ""))] = True
    found = []
    for group in main_groups:
        email = group["_source"].get("parentJson", {}).get("email", "")
        for child in group["_source"].get("child", []):
            item = parse(child)
            linkedin = item.get("linkedin", "")
            if (email, sha1(linkedin), item.get("date", "")) in wanted:
                found.append((group["_id"], child, linkedin))
    return found


def same_linkedin(child, linkedin):
    return parse(child).get("linkedin", "") == linkedin


def write_group(index, group_id, source, seq_no, primary_term):
    path = "/" + index + "/_doc/" + urllib.parse.quote(group_id, safe="") + "?refresh=true"
    if seq_no is None:
        path += "&op_type=create"
    else:
        path += "&if_seq_no=" + str(seq_no) + "&if_primary_term=" + str(primary_term)
    status, answer = call("PUT", path, source)
    return status in (200, 201), status, answer


def read_group(index, group_id):
    status, answer = call("GET", "/" + index + "/_doc/" + urllib.parse.quote(group_id, safe=""))
    if status != 200 or not answer.get("found"):
        return None
    return answer


groups_query = {"bool": {"filter": [{"term": {"parentName": PARENT_NAME}}, {"term": {"childName": CHILD_NAME}}]}}
main_groups = search_all(MAIN_GROUPER, groups_query)
twin_views = search_all(TWIN_VIEWS, {"match_all": {}})
moves = items_to_move(main_groups, twin_views)
print(f"{TWIN_VIEWS}\t{len(twin_views)} visualizacoes\t{MAIN_GROUPER}\t{len(main_groups)} grupos do mes\titens a mover\t{len(moves)}")

if simulate:
    print("simulacao: nada gravado")
    sys.exit(0)

failures = 0
for group_id, child, linkedin in moves:
    # 1. poe no grupo do jn_inactive_grouper (antes de tirar do jn_grouper: uma falha no meio nao perde o item)
    main = read_group(MAIN_GROUPER, group_id)
    if main is None or child not in main["_source"].get("child", []):
        continue
    twin = read_group(TWIN_GROUPER, group_id)
    if twin is None:
        twin_source = {key: value for key, value in main["_source"].items() if key not in ("child", "childCount")}
        twin_children = [child]
        twin_seq = (None, None)
    else:
        twin_source = dict(twin["_source"])
        twin_children = [other for other in twin_source.get("child", []) if not same_linkedin(other, linkedin)] + [child]
        twin_seq = (twin["_seq_no"], twin["_primary_term"])
    twin_source["child"] = twin_children
    twin_source["childCount"] = len(twin_children)
    written, status, answer = write_group(TWIN_GROUPER, group_id, twin_source, *twin_seq)
    if not written:
        failures += 1
        print("falha ao gravar um grupo do", TWIN_GROUPER, status, answer.get("error", {}).get("type"))
        continue
    # 2. tira do grupo do jn_grouper (grupo vazio e apagado, como o script removeChildByKeys)
    main_children = [other for other in main["_source"]["child"] if other != child]
    if not main_children:
        status, answer = call("DELETE", "/" + MAIN_GROUPER + "/_doc/" + urllib.parse.quote(group_id, safe="")
                              + "?refresh=true&if_seq_no=" + str(main["_seq_no"]) + "&if_primary_term=" + str(main["_primary_term"]))
        written = status in (200, 404)
    else:
        main_source = dict(main["_source"])
        main_source["child"] = main_children
        main_source["childCount"] = len(main_children)
        written, status, answer = write_group(MAIN_GROUPER, group_id, main_source, main["_seq_no"], main["_primary_term"])
    if not written:
        failures += 1
        print("falha ao tirar um item do", MAIN_GROUPER, status, answer.get("error", {}).get("type"))

remaining = items_to_move(search_all(MAIN_GROUPER, groups_query), twin_views)
twin_groups = search_all(TWIN_GROUPER, groups_query)
twin_items = sum(len(group["_source"].get("child", [])) for group in twin_groups)
print(f"movidos\t{len(moves) - len(remaining)}\tfalhas\t{failures}\trestam no {MAIN_GROUPER}\t{len(remaining)}"
      f"\t{TWIN_GROUPER}\t{len(twin_groups)} grupos, {twin_items} itens")
print("cache das entidades: 1 h; publique nova revisao da vis e reinicie os consumidores, ou espere a hora passar")
sys.exit(1 if failures or remaining else 0)
