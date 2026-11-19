"""So leitura: grava num arquivo JSON o resumo de cada curriculo ativo de producao (vis_resume), para escolher os que
combinam com o texto de uma vaga. Rodar por com-tunel-de-producao.ps1 (credencial em ES_DESTINO_AUTH):
  -Script este -Argumentos <arquivo de saida>
Cada item: linkedin, desiredJob, lastJob, resumeType, years (anos de experiencia, como o e-mail calcula), clt, pj, ddd,
skills (so as que o sistema nao descarta), notAllowedCompany, restricted (vis_resume_restriction), invalidLinkedin.
Nada e impresso alem de contagens.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:9210"
HEADERS = {"Content-Type": "application/json", "Authorization": os.environ["ES_DESTINO_AUTH"]}
TYPES = {1: "Tecnologia da Informacao", 2: "Recrutamento e selecao", 3: "Nivel Superior", 4: "Operacional"}


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


restricted = set()
try:
    restricted = {r["email"] for r in read_all("vis_resume_restriction", {"_source": ["email"], "query": {"match_all": {}}})}
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise

year = datetime.date.today().year
summaries = []
for resume in read_all("vis_resume", {"query": {"match_all": {}}}):
    experience = resume.get("experience")
    resume_type = resume.get("resumeType")
    skills = sorted({item.get("skill") for item in resume.get("skill") or []
                     if isinstance(item, dict) and item.get("category") != "discardedSkills" and item.get("skill")})
    summaries.append({
        "linkedin": resume.get("linkedinAddress"),
        "desiredJob": resume.get("desiredJob"),
        "lastJob": resume.get("lastJob"),
        "resumeType": TYPES.get(int(float(resume_type)), "?") if resume_type is not None else "?",
        "years": max(0, year - int(float(experience))) if experience is not None else None,
        "clt": resume.get("clt"),
        "pj": resume.get("pj"),
        "ddd": [int(float(ddd)) for ddd in resume.get("ddd") or []],
        "skills": skills,
        "notAllowedCompany": resume.get("notAllowedCompany") or [],
        "restricted": resume.get("email") in restricted,
        "invalidLinkedin": resume.get("invalidLinkedinAddress") is True,
    })

with open(sys.argv[1], "w", encoding="utf-8", newline="") as file:
    json.dump(summaries, file, ensure_ascii=False, indent=1)
print("curriculos ativos:", len(summaries), "| restritos:", sum(s["restricted"] for s in summaries),
      "| LinkedIn invalido:", sum(s["invalidLinkedin"] for s in summaries))
