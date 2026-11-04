"""Fase 5 do plano de migracao: copia do Elasticsearch de origem para o destino, por scroll e _bulk, com o mesmo _id.

Uso: python 10-copiar-dados.py <url da origem> <url do destino> [indice ...]
A credencial do destino vem da variavel ES_DESTINO_AUTH (o valor do cabecalho Authorization), nunca da linha de comando.
Nao altera a origem. Grava com a acao index: as sementes de vis_skill sao substituidas pelos registros com ranking.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

MAX_BULK_BYTES = 8 * 1024 * 1024
SCROLL_SIZE = 1000
EXCLUDED_SKILL = "LINUX EMBARCADO"
EXCLUDED_SKILLS = {EXCLUDED_SKILL, "PICK BY LIGHT"}
EXCLUDED_DOMAIN = "recrutadora.com.br"
GROUPER_PARENTS = {"vis_statis_skill_line_chart", "vis_statis_skill", "vis_statis_skill_pie_chart", "vis_virtual_recruiter_domain_initials_grouper"}
GROUPER_PARENTS_BY_SKILL = {"vis_statis_skill_line_chart", "vis_statis_skill"}
REAL_HIERARCHY_EMAILS = {"16911ce3b8bca2ebc4a7190231f140094834c419", "4f3b6ee8a84e4bdab624a23973679f7c836c7854"}
APPROVED_ITEMS = {("NOSQLDATABASE", "MEMCACHE", "add"), ("NOSQLDATABASE", "DATASTORE", "remove"), ("SQLDATABASE", "LINQ", "remove"),
                  ("JAVA SERVER", "JERSEY", "add"), ("ORMJAVA", "ORACLE", "add"), ("ORMJAVA", "JDBC", "add")}
REJECTED_ITEMS = {("SQLDATABASE", "ELASTICSEARCH", "add"), ("CACHE", "ELASTICSEARCH", "add"), ("ORMJAVA", "SPRING", "add"), ("ORMJAVA", "MYSQL", "add"),
                  ("AJAX", "EXTJS", "remove"), ("SQLDATABASE", "JPA", "remove"), ("SQLDATABASE", "HIBERNATE", "remove")}


def keeps_grouper(source):
    parent_name = source.get("parentName")
    if parent_name not in GROUPER_PARENTS:
        return False
    if parent_name not in GROUPER_PARENTS_BY_SKILL:
        return True
    parent_json = source.get("parentJson") or {}
    if isinstance(parent_json, str):
        parent_json = json.loads(parent_json)
    return parent_json.get("skill") != EXCLUDED_SKILL


def keeps_item(items):
    return lambda source: (source.get("parent"), source.get("skill"), source.get("type")) in items


# in the order of the plan: the indices 1 to 6, then 7 to 9; each one with its filter and the count expected in the end
PLAN = [
    ("vis_telegram_position", lambda source: True, 208891),
    ("vis_statis_skill_line_chart", lambda source: source.get("skill") != EXCLUDED_SKILL, 335814),
    ("vis_statis_skill_pie_chart", lambda source: True, 8737),
    ("jn_grouper", keeps_grouper, 387594),
    ("vis_skill", lambda source: source.get("skill") not in EXCLUDED_SKILLS, 1480),
    ("vis_recruiter", lambda source: source.get("domain") != EXCLUDED_DOMAIN, 44623),
    ("vis_skill_fix_hierarchy_fulfiled", lambda source: source.get("email") in REAL_HIERARCHY_EMAILS, 9),
    ("vis_skill_fix_hierarchy_item_approved", keeps_item(APPROVED_ITEMS), 6),
    ("vis_skill_fix_hierarchy_item_rejected", keeps_item(REJECTED_ITEMS), 7),
]


def call(method, url, body=None, raw=None, auth=None, attempts=5):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {"Content-Type": "application/x-ndjson" if raw is not None else "application/json"}
    if auth:
        headers["Authorization"] = auth
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as error:
            retry = error.code in (429, 502, 503, 504)
            if not retry or attempt == attempts - 1:
                raise SystemExit("%s %s: %s" % (method, error.code, error.read().decode("utf-8", "replace")[:600]))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == attempts - 1:
                raise SystemExit("%s falhou: %s" % (method, error))
        time.sleep(5 * (attempt + 1))
    raise SystemExit("sem resposta")


def send(destination, auth, lines):
    result = call("POST", destination + "/_bulk", raw=b"".join(lines), auth=auth)
    if not result.get("errors"):
        return
    failed = [item["index"] for item in result["items"] if "error" in item["index"]]
    raise SystemExit("bulk com %d falhas, primeira: %s" % (len(failed), json.dumps(failed[0])[:600]))


def copy(origin, destination, auth, name, keeps):
    result = call("POST", "%s/%s/_search?scroll=10m&size=%d" % (origin, name, SCROLL_SIZE), {"sort": ["_doc"]})
    read = sent = size = 0
    lines = []
    while result["hits"]["hits"]:
        for hit in result["hits"]["hits"]:
            read += 1
            if not keeps(hit["_source"]):
                continue
            action = json.dumps({"index": {"_index": name, "_id": hit["_id"]}})
            pair = (action + "\n" + json.dumps(hit["_source"], ensure_ascii=False) + "\n").encode("utf-8")
            if lines and size + len(pair) > MAX_BULK_BYTES:
                send(destination, auth, lines)
                lines, size = [], 0
            lines.append(pair)
            size += len(pair)
            sent += 1
        result = call("POST", origin + "/_search/scroll", {"scroll": "10m", "scroll_id": result["_scroll_id"]})
    if lines:
        send(destination, auth, lines)
    call("DELETE", origin + "/_search/scroll", {"scroll_id": result["_scroll_id"]})
    return read, sent


def main():
    origin, destination = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    chosen = set(sys.argv[3:])
    auth = os.environ.get("ES_DESTINO_AUTH")
    failures = 0
    started = time.time()
    for name, keeps, expected in PLAN:
        if chosen and name not in chosen:
            continue
        index_started = time.time()
        call("PUT", "%s/%s/_settings" % (destination, name), {"index": {"refresh_interval": "-1"}}, auth=auth)
        read, sent = copy(origin, destination, auth, name, keeps)
        call("PUT", "%s/%s/_settings" % (destination, name), {"index": {"refresh_interval": None}}, auth=auth)
        call("POST", "%s/%s/_refresh" % (destination, name), auth=auth)
        count = call("GET", "%s/%s/_count" % (destination, name), auth=auth)["count"]
        right = sent == expected
        failures += 0 if right else 1
        seconds = max(time.time() - index_started, 0.001)
        print("%s: lidos %d, enviados %d, esperado %d, no destino %d, %.0f s, %.0f docs/s, %s" % (name, read, sent, expected, count, seconds, sent / seconds, "OK" if right else "DIFERENTE"), flush=True)
    print("fim em %.0f s, indices diferentes do plano: %d" % (time.time() - started, failures), flush=True)
    sys.exit(1 if failures else 0)


main()
