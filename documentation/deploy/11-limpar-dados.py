"""Fase 6 do plano de migracao: tira LINUX EMBARCADO das vagas e dos grupos da pizza, e recrutadora.com.br do grupo REC.

Uso: python 11-limpar-dados.py <url da origem> <url do destino>
A credencial do destino vem da variavel ES_DESTINO_AUTH. Le a origem so para achar os ids excluidos do grafico de linhas.
Pode rodar de novo: o que ja foi editado nao entra na busca. Para antes de gravar se as contagens fugirem do plano.
"""
import json
import os
import sys
import urllib.error
import urllib.request

SKILL = "LINUX EMBARCADO"
DOMAIN = "recrutadora.com.br"
DOMAIN_GROUP_ID = "12623423b6e99a2f45d052daa02da12987882a2d"
PAGE_SIZE = 1000


def call(method, url, body=None, raw=None, auth=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {"Content-Type": "application/x-ndjson" if raw is not None else "application/json"}
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        raise SystemExit("%s %s: %s" % (method, error.code, error.read().decode("utf-8", "replace")[:600]))


def scan(base, auth, index, query):
    result = call("POST", "%s/%s/_search?scroll=5m&size=%d" % (base, index, PAGE_SIZE), {"query": query, "sort": ["_doc"]}, auth=auth)
    hits = []
    while result["hits"]["hits"]:
        hits.extend(result["hits"]["hits"])
        result = call("POST", base + "/_search/scroll", {"scroll": "5m", "scroll_id": result["_scroll_id"]}, auth=auth)
    call("DELETE", base + "/_search/scroll", {"scroll_id": result["_scroll_id"]}, auth=auth)
    return hits


def update(destination, auth, index, changes):
    lines = []
    for document_id, fields in changes:
        lines.append(json.dumps({"update": {"_index": index, "_id": document_id}}))
        lines.append(json.dumps({"doc": fields}, ensure_ascii=False))
    if not lines:
        return
    result = call("POST", destination + "/_bulk?refresh=true", raw=("\n".join(lines) + "\n").encode("utf-8"), auth=auth)
    if result.get("errors"):
        failed = [item["update"] for item in result["items"] if "error" in item["update"]]
        raise SystemExit("bulk com %d falhas, primeira: %s" % (len(failed), json.dumps(failed[0])[:600]))


def as_list(value):
    return value if isinstance(value, list) else [value]


def positions_changes(origin, destination, auth):
    excluded_ids = {hit["_id"] for hit in scan(origin, None, "vis_statis_skill_line_chart", {"term": {"skill": SKILL}})}
    print("ids excluidos do grafico de linhas: %d" % len(excluded_ids), flush=True)
    positions = scan(destination, auth, "vis_telegram_position", {"wildcard": {"skill": "*%s*" % SKILL}})
    changes = []
    removed_ids = 0
    for hit in positions:
        source = hit["_source"]
        skills = [skill for skill in source["skill"].split("_") if skill != SKILL]
        if not skills:
            raise SystemExit("vaga %s ficaria sem skill" % hit["_id"])
        charts = as_list(source.get("statisSkillLineChart", []))
        kept_charts = [chart for chart in charts if chart not in excluded_ids]
        removed_ids += len(charts) - len(kept_charts)
        changes.append((hit["_id"], {"skill": "_".join(skills), "statisSkillLineChart": kept_charts}))
    print("vagas: %d, ids tirados de statisSkillLineChart: %d" % (len(changes), removed_ids), flush=True)
    return changes


def pie_changes(destination, auth):
    groups = scan(destination, auth, "jn_grouper", {"term": {"parentName": "vis_statis_skill_pie_chart"}})
    changes = []
    for hit in groups:
        children = as_list(hit["_source"].get("child", []))
        kept = [child for child in children if json.loads(child).get("skill") != SKILL]
        if len(kept) == len(children):
            continue
        changes.append((hit["_id"], {"child": kept, "childCount": hit["_source"]["childCount"] - (len(children) - len(kept))}))
    print("grupos da pizza: %d de %d" % (len(changes), len(groups)), flush=True)
    return changes


def domain_change(destination, auth):
    source = call("GET", "%s/jn_grouper/_doc/%s" % (destination, DOMAIN_GROUP_ID), auth=auth)["_source"]
    children = as_list(source.get("child", []))
    if DOMAIN not in children:
        print("grupo REC ja sem %s, childCount %s" % (DOMAIN, source.get("childCount")), flush=True)
        return []
    kept = [child for child in children if child != DOMAIN]
    print("grupo REC: child de %d para %d, childCount %s" % (len(children), len(kept), source.get("childCount")), flush=True)
    return [(DOMAIN_GROUP_ID, {"child": kept, "childCount": source["childCount"] - 1})]


def main():
    origin, destination = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    auth = os.environ.get("ES_DESTINO_AUTH")
    positions = positions_changes(origin, destination, auth)
    pies = pie_changes(destination, auth)
    domains = domain_change(destination, auth)
    # the expected counts come from the origin, since a reload of the positions changes them (21 and 12 in the plan)
    expected_positions = call("POST", origin + "/vis_telegram_position/_count", {"query": {"wildcard": {"skill": "*%s*" % SKILL}}})["count"]
    expected_pies = len(pie_changes(origin, None))
    print("esperado pela origem: vagas %d, pizza %d" % (expected_positions, expected_pies), flush=True)
    limits = (len(positions) in (0, expected_positions), len(pies) in (0, expected_pies), len(domains) in (0, 1))
    if not all(limits):
        raise SystemExit("contagens fora do plano; nada foi gravado: vagas %d, pizza %d, dominio %d" % (len(positions), len(pies), len(domains)))
    update(destination, auth, "vis_telegram_position", positions)
    update(destination, auth, "jn_grouper", pies + domains)
    left = call("POST", destination + "/vis_telegram_position/_count", {"query": {"wildcard": {"skill": "*%s*" % SKILL}}}, auth=auth)["count"]
    print("gravado; vagas ainda com o termo: %d" % left, flush=True)


main()
