# E-mail dos curriculos de uma vaga (2026-11-27): o recrutador cujo e-mail esta no texto de uma vaga (/salvarVaga ou
# grupo do bot support) deixa de receber o e-mail diario de curriculos (VisNotifyRecruiterAboutResumes) e passa a receber
# o e-mail proprio da vaga (VisNotifyRecruiterAboutResumesOfTheJobPosting): o texto da vaga no lugar da frase dos ultimos
# 7 dias, sem "ver todos", e o assunto "{n} curriculos encontrados para o anuncio de vaga {1a linha}" (no singular,
# "curriculo encontrado para o anuncio de vaga {1a linha}"). O banner amarelo dos dois e-mails passa a anunciar que cada
# vaga cadastrada recebe os curriculos aderentes, com o link {frontendUrl}/curriculos/vagas-cadastradas.
#
# O que faz, com o mesmo _id do codigo (134-sementes-email-dos-curriculos-da-vaga.jsonl, gerado por
# DumpJobPostingEmailSeeds.java a partir do getFirstRecordsToInsert de VisEntityRecruiterResumes):
#   1. regra "igual": grava os 2 templates do e-mail da vaga (portugues e ingles) e os 4 textos do assunto
#      (VisRecruiterResumesTexts.jobPostingSubjectOne/Many) em jn_system_message;
#   2. regra "adaptar": grava os parametros de envio do e-mail da vaga com o sender e o moreParameters copiados dos
#      parametros do e-mail diario (VisNotifyRecruiterAboutResumes) do proprio destino (enderecos de producao);
#   3. no template do e-mail diario do destino troca SO o banner antigo pelo novo (o resto do texto de producao fica como
#      esta); ja trocado, pula; sem o banner antigo nem o novo, falha sem gravar.
# Idempotente. Confere o que gravou. Roda ANTES do deploy dos consumidores (o e-mail da vaga sai no consumidor da fila de
# VisEntityJobPosting e na resposta das vagas dos grupos); o banner do e-mail diario vale a partir da gravacao. Depois:
# cache das entidades de 1 h (reiniciar os consumidores no deploy resolve).
# Uso: ES_DESTINO_AUTH=<valor do Authorization> python -I 134-email-dos-curriculos-da-vaga.py [destino]
#      ou: & .\com-tunel-de-producao.ps1 -Script .\134-email-dos-curriculos-da-vaga.py
#      (sem destino: o tunel de producao, http://127.0.0.1:9210; para o ES local, http://127.0.0.1:9200)
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

arguments = [argument for argument in sys.argv[1:] if not argument.startswith("--")]
target_url = arguments[0].rstrip("/") if arguments else "http://127.0.0.1:9210"
auth = os.environ.get("ES_DESTINO_AUTH", "")
here = os.path.dirname(os.path.abspath(__file__))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

SEEDS_FILE = os.path.join(here, "134-sementes-email-dos-curriculos-da-vaga.jsonl")
DAILY = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumes"
JOB_POSTING = "com.vis.messages.VisMessages$VisNotifyRecruiterAboutResumesOfTheJobPosting"
BOX = ("<p style=\"background-color: #FFF4CC; border-left: 6px solid #F5A623; padding: 12px 16px; "
       "font-size: 17px; font-weight: bold; color: #333333;\">&#128226; ")
OLD_BANNERS = {
    "portuguese": BOX + "Ainda este ano você poderá, <span style=\"color: #D35400;\">gratuitamente</span>, "
                  "cadastrar vagas e receber apenas currículos consistentes!</p>",
    "english": BOX + "Later this year you will be able, <span style=\"color: #D35400;\">for free</span>, "
               "to post positions and receive only consistent resumes!</p>",
}


def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(target_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if auth:
        request.add_header("Authorization", auth)
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def get(index, record_id):
    status, answer = call("GET", "/%s/_doc/%s" % (index, urllib.parse.quote(record_id, safe="")))
    return answer.get("_source") if status == 200 else None


def put(index, record_id, source):
    status, answer = call("PUT", "/%s/_doc/%s?refresh=true" % (index, urllib.parse.quote(record_id, safe="")), source)
    return status in (200, 201), answer


status, cluster = call("GET", "/")
print("cluster:", cluster.get("cluster_name"))
with open(SEEDS_FILE, encoding="utf-8") as seeds_file:
    seeds = [json.loads(line) for line in seeds_file if line.strip()]
failures = 0

# os parametros do e-mail diario do destino: de onde vem o sender e o moreParameters do e-mail da vaga
status, found = call("POST", "/jn_email_parameters_to_send/_search",
                     {"size": 100, "query": {"match_all": {}}})
daily_parameters = [hit["_source"] for hit in found["hits"]["hits"] if hit["_source"].get("templateId") == DAILY]
if len(daily_parameters) != 1:
    print("parametros do e-mail diario: esperado 1, achados", len(daily_parameters), "- nada gravado")
    sys.exit(1)
daily_parameters = daily_parameters[0]

for seed in seeds:
    index, record_id, source = seed["index"], seed["id"], seed["source"]
    name = source.get("templateId") or source.get("systemMessageName")
    label = "%s %s %s" % (index, name.rsplit(".", 1)[-1], source.get("language", ""))
    if index == "jn_email_template_message" and source["templateId"] == DAILY:
        # 3. so o banner do e-mail diario
        current = get(index, record_id)
        if current is None:
            print(label, ": template diario nao existe no destino - FALHA")
            failures += 1
            continue
        language = source["language"]
        old_banner = OLD_BANNERS[language]
        new_banner = source["message"][source["message"].index(BOX):]
        new_banner = new_banner[:new_banner.index("</p>") + len("</p>")]
        message = current["message"]
        if new_banner in message:
            print(label, ": banner novo ja gravado, pulado")
            continue
        if old_banner not in message:
            print(label, ": sem o banner antigo nem o novo - FALHA, nada gravado")
            failures += 1
            continue
        changed = dict(current, message=message.replace(old_banner, new_banner))
        ok, answer = put(index, record_id, changed)
        reread = get(index, record_id) or {}
        ok = ok and new_banner in reread.get("message", "") and old_banner not in reread.get("message", "")
        print(label, ": banner trocado" if ok else ": FALHA " + json.dumps(answer)[:300])
        failures += 0 if ok else 1
        continue
    if index == "jn_email_parameters_to_send":
        # 2. adaptar: os campos de ambiente do e-mail diario do destino
        source = dict(source, sender=daily_parameters["sender"], moreParameters=daily_parameters["moreParameters"])
    # 1. igual (e o 2, ja adaptado)
    ok, answer = put(index, record_id, source)
    reread = get(index, record_id)
    ok = ok and reread == source
    print(label, ": gravado e conferido" if ok else ": FALHA " + json.dumps(answer)[:300])
    failures += 0 if ok else 1

print("falhas:", failures)
sys.exit(1 if failures else 0)
