"""Refaz as fases 5, 6 e 8 do plano de migracao para os dados que mudam com o synonyms.json e com a recarga do Telegram,
sem repetir a fase 4: as sementes e os demais indices da producao ficam como estao.

Apaga no destino os documentos de vis_telegram_position, vis_statis_skill_line_chart, vis_statis_skill_pie_chart e
vis_skill, e os grupos do jn_grouper de vis_statis_skill*, vis_virtual_recruiter_domain_initials_grouper e
vis_virtual_skill_initials_grouper; copia de novo pelo 10-copiar-dados.py; grava os grupos de iniciais das skills sem os
ids das skills excluidas (os mesmos que a semente gravaria); limpa pelo 11-limpar-dados.py e varre pelo 12.

Uso: python 21-refazer-dados-das-vagas.py <url da origem> <url do destino>
A credencial do destino vem da variavel ES_DESTINO_AUTH. Nao altera a origem.
Para sem apagar nada se o destino tiver dados de usuario (login, curriculo, fale conosco).
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EXCLUDED_SKILLS = {"LINUX EMBARCADO", "PICK BY LIGHT"}
SKILL_INITIALS = "vis_virtual_skill_initials_grouper"
REPLACED_INDICES = ["vis_telegram_position", "vis_statis_skill_line_chart", "vis_statis_skill_pie_chart", "vis_skill"]
REPLACED_GROUPS = ["vis_statis_skill_line_chart", "vis_statis_skill", "vis_statis_skill_pie_chart",
                   "vis_virtual_recruiter_domain_initials_grouper", SKILL_INITIALS]
USER_DATA = ["js_login_password", "js_login_token", "jn_login_email", "vis_resume", "js_contact_us", "js_contact_us_solved"]
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(method, url, body=None, raw=None, auth=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    headers = {"Content-Type": "application/x-ndjson" if raw is not None else "application/json"}
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with opener.open(request, timeout=300) as response:
            return json.loads(response.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as error:
        raise SystemExit("%s %s %s: %s" % (method, url, error.code, error.read().decode("utf-8", "replace")[:600]))


def count(base, auth, index, query=None):
    body = {"query": query} if query else None
    return call("POST", "%s/%s/_count" % (base, index), body, auth=auth)["count"]


def delete_by_query(destination, auth, index, query):
    url = "%s/%s/_delete_by_query?conflicts=proceed&refresh=true&slices=auto&wait_for_completion=false" % (destination, index)
    task = call("POST", url, {"query": query}, auth=auth)["task"]
    while True:
        time.sleep(5)
        status = call("GET", "%s/_tasks/%s" % (destination, task), auth=auth)
        if status.get("completed"):
            response = status.get("response", {})
            if response.get("failures"):
                raise SystemExit("delete_by_query em %s com falhas: %s" % (index, json.dumps(response["failures"])[:600]))
            print("%s: apagados %s" % (index, response.get("deleted")), flush=True)
            return


def scan(base, index, query):
    result = call("POST", "%s/%s/_search?scroll=5m&size=1000" % (base, index), {"query": query, "sort": ["_doc"]})
    hits = []
    while result["hits"]["hits"]:
        hits.extend(result["hits"]["hits"])
        result = call("POST", base + "/_search/scroll", {"scroll": "5m", "scroll_id": result["_scroll_id"]})
    call("DELETE", base + "/_search/scroll", {"scroll_id": result["_scroll_id"]})
    return hits


def copy_skill_initials(origin, destination, auth):
    excluded_ids = {hit["_id"] for hit in scan(origin, "vis_skill", {"terms": {"skill": sorted(EXCLUDED_SKILLS)}})}
    if len(excluded_ids) != len(EXCLUDED_SKILLS):
        raise SystemExit("skills excluidas achadas na origem: %d" % len(excluded_ids))
    groups = scan(origin, "jn_grouper", {"term": {"parentName": SKILL_INITIALS}})
    lines = []
    edited = dropped = 0
    for hit in groups:
        source = dict(hit["_source"])
        children = source.get("child", [])
        kept = [child for child in children if child not in excluded_ids]
        if not kept:
            dropped += 1
            continue
        if len(kept) != len(children):
            edited += 1
            source["child"] = kept
            source["childCount"] = len(kept)
        lines.append(json.dumps({"index": {"_index": "jn_grouper", "_id": hit["_id"]}}))
        lines.append(json.dumps(source, ensure_ascii=False))
    result = call("POST", destination + "/_bulk?refresh=true", raw=("\n".join(lines) + "\n").encode("utf-8"), auth=auth)
    if result.get("errors"):
        raise SystemExit("bulk dos grupos de iniciais com falhas")
    print("grupos de iniciais: origem %d, enviados %d, editados %d, descartados %d" % (len(groups), len(lines) // 2, edited, dropped), flush=True)


def run(script, *arguments):
    print("== %s %s" % (script, " ".join(arguments)), flush=True)
    code = subprocess.call([sys.executable, "-I", os.path.join(HERE, script)] + list(arguments))
    if code != 0:
        raise SystemExit("%s saiu com %d" % (script, code))


def main():
    origin, destination = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    auth = os.environ.get("ES_DESTINO_AUTH")
    users = {index: count(destination, auth, index) for index in USER_DATA}
    if any(users.values()):
        raise SystemExit("o destino tem dados de usuario, nada foi apagado: %s" % users)
    for index in REPLACED_INDICES:
        delete_by_query(destination, auth, index, {"match_all": {}})
    delete_by_query(destination, auth, "jn_grouper", {"terms": {"parentName": REPLACED_GROUPS}})
    run("10-copiar-dados.py", origin, destination, *REPLACED_INDICES[:3], "jn_grouper", "vis_skill")
    copy_skill_initials(origin, destination, auth)
    run("11-limpar-dados.py", origin, destination)
    run("12-varrer-skills-excluidas.py", destination)
    for index in REPLACED_INDICES + ["jn_grouper"]:
        print("%s no destino: %d" % (index, count(destination, auth, index)), flush=True)


main()
