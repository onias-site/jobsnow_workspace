"""So leitura: le do Elasticsearch de producao (tunel IAP na porta 9210) o que o e-mail de curriculos aos recrutadores usa
e grava tudo num arquivo JSON, para o SendProductionResumesToRecruiter.java montar o e-mail sem tocar em producao.

Conteudo do arquivo:
  resumes         todos os registros de vis_resume, como estao gravados
  rankings        skill -> ranking de vis_skill, so das skills desses curriculos
  dates           hash do e-mail do curriculo -> [insercao, ultima alteracao], do historico (jn_versionable)
  lastViewByPair  "hash do e-mail do recrutador|hash do LinkedIn" -> ultima visualizacao, do historico
  aliasByPair     "hash do e-mail do recrutador|hash do LinkedIn" -> apelido, de vis_viewed_resume
  inactivePairs   ["hash do e-mail do recrutador|hash do LinkedIn"], de vis_inactive_viewed_resume (curriculos que nao vao mais ao recrutador)

Rodar por com-tunel-de-producao.ps1 (a credencial vem de ES_DESTINO_AUTH): -Script este -Argumentos <arquivo de saida>
Nenhum e-mail ou valor de registro e impresso, so contagens.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:9210"
HEADERS = {"Content-Type": "application/json", "Authorization": os.environ["ES_DESTINO_AUTH"]}


def post(path, body):
    request = urllib.request.Request(BASE + path, data=json.dumps(body).encode("utf-8"), headers=HEADERS, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def read_all(index, body):
    result = post("/" + index + "/_search?scroll=2m", dict(body, size=500))
    sources = []
    while result["hits"]["hits"]:
        sources.extend(hit["_source"] for hit in result["hits"]["hits"])
        result = post("/_search/scroll", {"scroll": "2m", "scroll_id": result["_scroll_id"]})
    return sources


def history_of(entity):
    rows = read_all("jn_versionable", {"_source": ["json", "timestamp"], "query": {"term": {"entity": entity}}})
    return [(json.loads(row["json"]), int(row["timestamp"])) for row in rows]


target = sys.argv[1]
cluster = post("/_search?size=0&filter_path=took", {})
resumes = read_all("vis_resume", {"query": {"match_all": {}}})
# os curriculos restritos (vis_resume_restriction, desde 2026-11-12) nao vao a recrutador nenhum, como no processo diario
restricted_emails = set()
try:
    for restriction in read_all("vis_resume_restriction", {"_source": ["email"], "query": {"match_all": {}}}):
        restricted_emails.add(restriction["email"])
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
all_resumes = len(resumes)
# o LinkedIn invalido confirmado pelo suporte (invalidLinkedinAddress, desde 2026-11-12) tambem fica fora, como no
# getResumes do processo diario
resumes = [resume for resume in resumes
           if resume.get("email") not in restricted_emails and resume.get("invalidLinkedinAddress") is not True]

skills = sorted({item["skill"] for resume in resumes for item in resume.get("skill", [])})
rankings = {}
for start in range(0, len(skills), 500):
    chunk = skills[start:start + 500]
    found = read_all("vis_skill", {"_source": ["skill", "ranking"], "query": {"terms": {"skill": chunk}}})
    for skill in found:
        if "ranking" in skill:
            rankings[skill["skill"]] = skill["ranking"]

dates = {}
for record, timestamp in history_of("vis_resume"):
    oldest_and_newest = dates.setdefault(record["email"], [timestamp, timestamp])
    oldest_and_newest[0] = min(oldest_and_newest[0], timestamp)
    oldest_and_newest[1] = max(oldest_and_newest[1], timestamp)

last_view_by_pair = {}
for record, timestamp in history_of("vis_viewed_resume"):
    pair = record["email"] + "|" + record["linkedin"]
    last_view_by_pair[pair] = max(last_view_by_pair.get(pair, 0), timestamp)

alias_by_pair = {}
for view in read_all("vis_viewed_resume", {"_source": ["email", "linkedin", "alias"], "query": {"match_all": {}}}):
    if "alias" in view:
        alias_by_pair[view["email"] + "|" + view["linkedin"]] = view["alias"]

# a gemea de vis_viewed_resume (desde 2026-11-12): o curriculo de cada par nao vai mais ao recrutador; antes do script 62
# o indice nao existe em producao, e a lista fica vazia
inactive_pairs = []
try:
    for view in read_all("vis_inactive_viewed_resume", {"_source": ["email", "linkedin"], "query": {"match_all": {}}}):
        inactive_pairs.append(view["email"] + "|" + view["linkedin"])
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise

content = {"resumes": resumes, "rankings": rankings, "dates": dates, "lastViewByPair": last_view_by_pair, "aliasByPair": alias_by_pair,
           "inactivePairs": inactive_pairs}
with open(target, "w", encoding="utf-8", newline="") as file:
    json.dump(content, file, ensure_ascii=False)
print("curriculos:", len(resumes), "de", all_resumes, "(restritos e LinkedIn invalido fora)", "| skills com ranking:", len(rankings), "de", len(skills),
      "| curriculos com datas:", len(dates), "| pares visualizados:", len(last_view_by_pair), "| apelidos:", len(alias_by_pair), "| pares inativos:", len(inactive_pairs))
